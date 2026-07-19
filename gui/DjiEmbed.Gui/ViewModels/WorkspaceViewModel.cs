using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// The single-window workspace (GUI 2.0 spec 2026-07-18): source + mode
/// strip + action on the left; the right pane's idle/running/done/failed
/// states are driven by the inherited <see cref="FlowStep"/>.
/// </summary>
public partial class WorkspaceViewModel : FlowViewModel
{
    private readonly IMapServer _mapServer;
    private readonly Action _openCliDiscovery;
    private readonly Func<string?>? _cliResolver;
    private readonly Func<bool> _previewAvailable;

    public WorkspaceViewModel(string? cli, DjiEmbedRunner runner,
        IMapServer mapServer, Action openCliDiscovery,
        Func<string?>? cliResolver = null,
        Func<bool>? previewAvailable = null)
        : base(cli, runner, static () => { })
    {
        _mapServer = mapServer;
        _openCliDiscovery = openCliDiscovery;
        _cliResolver = cliResolver;
        _previewAvailable = previewAvailable
            ?? (static () => WebViewSupport.IsLikelyAvailable);
    }

    public IReadOnlyList<WorkspaceMode> Modes => WorkspaceMode.All;

    [ObservableProperty]
    public partial string? SelectedFolder { get; set; }

    [ObservableProperty]
    public partial WorkspaceMode SelectedMode { get; set; } = WorkspaceMode.All[0];

    [ObservableProperty]
    public partial WorkspaceMode? SuggestedMode { get; set; }

    [ObservableProperty]
    public partial bool AllGood { get; set; }

    public ObservableCollection<SetupItem> SetupItems { get; } = [];

    /// <summary>The action button lights up as soon as a run could work.</summary>
    public bool CanRun => !SelectedMode.NeedsFolder || SelectedFolder is not null;

    partial void OnSelectedFolderChanged(string? value)
    {
        OnPropertyChanged(nameof(CanRun));
        RunCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedModeChanged(WorkspaceMode value)
    {
        OnPropertyChanged(nameof(CanRun));
        RunCommand.NotifyCanExecuteChanged();
    }

    protected override string GenericFailureMessage =>
        SelectedMode.FailureMessage;

    /// <summary>
    /// Folder drop/pick: remember it, suggest the likely mode. A new folder
    /// is a fresh start — Done/Failed flip back to the idle pane. Ignored
    /// while a run is in flight.
    /// </summary>
    public async Task SetFolderAsync(string folder)
    {
        if (Step == FlowStep.Running)
        {
            return;
        }
        SelectedFolder = folder;
        var contents = await Task.Run(() => FolderInspector.Inspect(folder));
        SuggestedMode =
            contents.HasFlightLogs ? WorkspaceMode.Of(WorkspaceModeKind.FlightMap)
            : contents.HasPhotos ? WorkspaceMode.Of(WorkspaceModeKind.PhotoMap)
            : contents.HasVideos ? WorkspaceMode.Of(WorkspaceModeKind.Embed)
            : null;
        if (SuggestedMode is not null)
        {
            SelectedMode = SuggestedMode;
        }
        Step = FlowStep.Pick;
    }

    [RelayCommand]
    private void ClearFolder()
    {
        SelectedFolder = null;
        SuggestedMode = null;
    }

    [RelayCommand]
    private void OpenCliDiscovery() => _openCliDiscovery();

    /// <summary>"Process another": back to idle, keep folder and mode.</summary>
    protected override void GoHomeCore() => Step = FlowStep.Pick;

    [RelayCommand(CanExecute = nameof(CanRun))]
    private async Task RunAsync()
    {
        CliPath ??= _cliResolver?.Invoke();
        if (!EnsureCli())
        {
            return;
        }
        SetupItems.Clear();
        AllGood = false;
        if (SelectedMode.Kind == WorkspaceModeKind.Setup)
        {
            await RunSetupAsync();
            return;
        }
        if (SelectedFolder is not { } folder)
        {
            return;
        }
        var contents = await Task.Run(() => FolderInspector.Inspect(folder));
        switch (SelectedMode.Kind)
        {
            case WorkspaceModeKind.FlightMap when !contents.HasFlightLogs:
                Fail("No drone flight logs (.SRT) were found in that folder. "
                     + "Pick the folder that contains your footage — "
                     + "subfolders are included automatically.");
                return;
            case WorkspaceModeKind.FlightMap:
                await ExecuteFlowAsync(() => RunStepAsync(
                    "Mapping your flights…", ["flightmap", folder, "-r"]));
                return;
            case WorkspaceModeKind.PhotoMap when !contents.HasPhotos:
                Fail("No photos were found in that folder. Pick the folder "
                     + "that contains your pictures — subfolders are "
                     + "included automatically.");
                return;
            case WorkspaceModeKind.PhotoMap:
                // --link-originals: the map is written inside the mapped
                // folder, so the relative links are stable there — and they
                // power the embedded 360° panorama viewer (#305).
                await ExecuteFlowAsync(() => RunStepAsync(
                    "Mapping your photos…",
                    ["photomap", folder, "-r", "--link-originals"]));
                return;
            case WorkspaceModeKind.Embed when !contents.HasVideos:
                Fail("No videos (.MP4) were found in that folder. Pick the "
                     + "folder that holds the drone videos together with "
                     + "their .SRT flight logs.");
                return;
            case WorkspaceModeKind.Embed:
                await ExecuteFlowAsync(() => RunStepAsync(
                    "Embedding flight data into new copies…",
                    ["embed", folder]));
                return;
        }
    }

    private Task RunSetupAsync() => ExecuteFlowAsync(async () =>
    {
        var result = await RunCliAsync("Checking…", ["doctor"]);
        if (result.ExitCode != 0
            || result.Terminal is not { Kind: ProgressEventKind.Result } t)
        {
            Fail(result.Terminal?.Message ?? GenericFailureMessage,
                string.IsNullOrWhiteSpace(result.StderrText)
                    ? null : result.StderrText);
            return false;
        }
        foreach (var item in DoctorReport.Parse(t.Summary))
        {
            SetupItems.Add(item);
        }
        AllGood = t.Ok == true;
        return true;
    });

    /// <summary>
    /// HTML maps open through the managed local server instead of file://,
    /// which blocks the 360° panorama viewer (#305). A server that fails to
    /// start falls back to the plain file open.
    /// </summary>
    protected override async Task OpenOutputCoreAsync(string path)
    {
        if (CliPath is not null
            && path.EndsWith(".html", StringComparison.OrdinalIgnoreCase))
        {
            var url = await _mapServer.GetUrlAsync(CliPath, path);
            if (url is not null)
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
                return;
            }
        }
        await base.OpenOutputCoreAsync(path);
    }
}
