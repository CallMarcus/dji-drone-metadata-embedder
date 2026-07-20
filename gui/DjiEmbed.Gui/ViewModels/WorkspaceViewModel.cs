using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Threading;
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
        FlightOptions.PropertyChanged += (_, _) =>
            OnPropertyChanged(nameof(CommandPreview));
    }

    /// <summary>Curated option state for the Flight map mode (M3b). Feeds both
    /// the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public FlightMapOptionsViewModel FlightOptions { get; } = new();

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

    [ObservableProperty]
    public partial string? PreviewUrl { get; set; }

    [ObservableProperty]
    public partial string? PreviewPath { get; set; }

    /// <summary>A map was made but the inline preview can't render here —
    /// the done-card explains once, calmly.</summary>
    [ObservableProperty]
    public partial bool PreviewUnavailable { get; set; }

    /// <summary>Done pane, card flavour (setup, embed, degraded maps).</summary>
    public bool ShowDoneCard => Step == FlowStep.Done && PreviewUrl is null;

    /// <summary>Done pane, inline-map flavour.</summary>
    public bool ShowPreview => Step == FlowStep.Done && PreviewUrl is not null;

    protected override void OnStepChangedCore(FlowStep value)
    {
        OnPropertyChanged(nameof(ShowDoneCard));
        OnPropertyChanged(nameof(ShowPreview));
    }

    partial void OnPreviewUrlChanged(string? value)
    {
        OnPropertyChanged(nameof(ShowDoneCard));
        OnPropertyChanged(nameof(ShowPreview));
    }

    /// <summary>The action button lights up as soon as a run could work.</summary>
    public bool CanRun => !SelectedMode.NeedsFolder || SelectedFolder is not null;

    /// <summary>Whether the Flight map options panel applies to the current mode.</summary>
    public bool IsFlightMapMode => SelectedMode.Kind == WorkspaceModeKind.FlightMap;

    /// <summary>
    /// The exact human-facing <c>dji-embed</c> command the current mode +
    /// folder would run — the CLI transparency strip (GUI 2.0 spec, M3a).
    /// Uses a <c>&lt;folder&gt;</c> placeholder before a folder is picked so
    /// the strip teaches the command shape from the idle state. Never shows
    /// <c>--progress jsonl</c> (an execution detail added by the runner).
    /// </summary>
    public string CommandPreview
    {
        get
        {
            var folder = SelectedFolder
                ?? (SelectedMode.NeedsFolder ? "<folder>" : null);
            // folder! is safe for Flight map: its NeedsFolder is true, so the
            // line above yields the "<folder>" placeholder (never null) when
            // no folder is picked.
            var argv = SelectedMode.Kind == WorkspaceModeKind.FlightMap
                ? CommandBuilder.FlightMap(folder!, FlightOptions.ToOptions())
                : CommandBuilder.Build(SelectedMode.Kind, folder);
            return CommandLine.Format("dji-embed", argv);
        }
    }

    partial void OnSelectedFolderChanged(string? value)
    {
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        RunCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedModeChanged(WorkspaceMode value)
    {
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        OnPropertyChanged(nameof(IsFlightMapMode));
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
        ResetPreview();
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

    [RelayCommand]
    private void ShowInFolder()
    {
        if (PreviewPath is not null)
        {
            Reveal.InFolder(PreviewPath);
        }
    }

    /// <summary>"Process another": back to idle, keep folder and mode.</summary>
    protected override void GoHomeCore()
    {
        ResetPreview();
        Step = FlowStep.Pick;
    }

    private void ResetPreview()
    {
        PreviewUrl = null;
        PreviewPath = null;
        PreviewUnavailable = false;
    }

    /// <summary>
    /// After a successful map run: point the pane's WebView at the first
    /// HTML output over the local server (#305 — file:// blocks the pano
    /// viewer). Runs inside the flow so Done appears with the URL already
    /// in hand; a preview that can't happen never fails the run.
    /// </summary>
    private async Task<bool> PrimePreviewAsync()
    {
        string? html = null;
        foreach (var output in Outputs)
        {
            if (output.EndsWith(".html", StringComparison.OrdinalIgnoreCase))
            {
                html = output;
                break;
            }
        }
        if (html is null)
        {
            return true;
        }
        try
        {
            if (!_previewAvailable() || CliPath is null)
            {
                PreviewUnavailable = true;
                return true;
            }
            var url = await _mapServer.GetUrlAsync(CliPath, html, FlowToken);
            if (url is null)
            {
                PreviewUnavailable = true;
                return true;
            }
            PreviewPath = html;      // path first: the view reads it when the URL lands
            PreviewUrl = url;
        }
        catch (OperationCanceledException)
        {
            throw;   // ExecuteFlowAsync maps this to Step = Pick.
        }
        catch (Exception)
        {
            PreviewUnavailable = true;
        }
        return true;
    }

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
            ResetPreview();
            await RunSetupAsync();
            return;
        }
        if (SelectedFolder is not { } folder)
        {
            return;
        }
        var contents = await Task.Run(() => FolderInspector.Inspect(folder));
        // Reset only now, past the awaited scan: clearing the preview any
        // earlier flashes the stale done card while a live map is still up.
        ResetPreview();
        switch (SelectedMode.Kind)
        {
            case WorkspaceModeKind.FlightMap when !contents.HasFlightLogs:
                Fail("No drone flight logs (.SRT) were found in that folder. "
                     + "Pick the folder that contains your footage — "
                     + "subfolders are included automatically.");
                return;
            case WorkspaceModeKind.FlightMap:
                await ExecuteFlowAsync(async () =>
                    await RunStepAsync(
                        "Mapping your flights…",
                        CommandBuilder.FlightMap(folder, FlightOptions.ToOptions()))
                    && await PrimePreviewAsync());
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
                await ExecuteFlowAsync(async () =>
                    await RunStepAsync(
                        "Mapping your photos…",
                        CommandBuilder.Build(SelectedMode.Kind, folder))
                    && await PrimePreviewAsync());
                return;
            case WorkspaceModeKind.Embed when !contents.HasVideos:
                Fail("No videos (.MP4) were found in that folder. Pick the "
                     + "folder that holds the drone videos together with "
                     + "their .SRT flight logs.");
                return;
            case WorkspaceModeKind.Embed:
                await ExecuteFlowAsync(() => RunStepAsync(
                    "Embedding flight data into new copies…",
                    CommandBuilder.Build(SelectedMode.Kind, folder)));
                return;
        }
    }

    private Task RunSetupAsync() => ExecuteFlowAsync(async () =>
    {
        var result = await RunCliAsync(
            "Checking…", CommandBuilder.Build(WorkspaceModeKind.Setup, null));
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
            // Opening an output isn't part of a flow — nothing cancels it.
            var url = await _mapServer.GetUrlAsync(
                CliPath, path, CancellationToken.None);
            if (url is not null)
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
                return;
            }
        }
        await base.OpenOutputCoreAsync(path);
    }
}
