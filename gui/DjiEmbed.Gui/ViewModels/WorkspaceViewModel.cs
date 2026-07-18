using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
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
    private readonly MapServer _mapServer;
    private readonly Action _openCliDiscovery;

    public WorkspaceViewModel(string? cli, DjiEmbedRunner runner,
        MapServer mapServer, Action openCliDiscovery)
        : base(cli, runner, static () => { })
    {
        _mapServer = mapServer;
        _openCliDiscovery = openCliDiscovery;
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

    partial void OnSelectedFolderChanged(string? value) =>
        OnPropertyChanged(nameof(CanRun));

    partial void OnSelectedModeChanged(WorkspaceMode value) =>
        OnPropertyChanged(nameof(CanRun));

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
}
