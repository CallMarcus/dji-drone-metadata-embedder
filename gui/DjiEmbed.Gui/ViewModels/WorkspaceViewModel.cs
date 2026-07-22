using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
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
    private readonly Func<string, FolderContents> _inspectFolder;
    private readonly GuiStateStore _stateStore;

    public WorkspaceViewModel(string? cli, DjiEmbedRunner runner,
        IMapServer mapServer, Action openCliDiscovery,
        Func<string?>? cliResolver = null,
        Func<bool>? previewAvailable = null,
        Func<string, FolderContents>? folderInspector = null,
        GuiStateStore? stateStore = null)
        : base(cli, runner, static () => { })
    {
        _mapServer = mapServer;
        _openCliDiscovery = openCliDiscovery;
        _cliResolver = cliResolver;
        _previewAvailable = previewAvailable
            ?? (static () => WebViewSupport.IsLikelyAvailable);
        // The folder scan is injectable (#340): FolderInspector is static
        // and deliberately has no early exit, so only a seam lets a test
        // hold a scan open and prove the busy window is closed.
        _inspectFolder = folderInspector ?? FolderInspector.Inspect;
        FlightOptions.PropertyChanged += (_, _) =>
            OnPropertyChanged(nameof(CommandPreview));
        PhotoOptions.PropertyChanged += (_, _) =>
        {
            OnPropertyChanged(nameof(CommandPreview));
            OnPropertyChanged(nameof(PhotoLinksCannotReachOriginals));
        };
        EmbedOptions.PropertyChanged += (_, _) =>
            OnPropertyChanged(nameof(CommandPreview));
        ConvertOptions.PropertyChanged += (_, _) =>
            OnPropertyChanged(nameof(CommandPreview));
        VerifyOptions.PropertyChanged += (_, _) =>
        {
            OnPropertyChanged(nameof(CommandPreview));
            OnPropertyChanged(nameof(ActionVerb));
        };
        Warnings.CollectionChanged += (_, _) =>
            OnPropertyChanged(nameof(ShowDoneWarnings));
        VerifyCards.CollectionChanged += (_, _) =>
            OnPropertyChanged(nameof(ShowDoneWarnings));

        _stateStore = stateStore ?? GuiStateStore.Ephemeral();
        foreach (var f in _stateStore.ExistingRecents())
        {
            RecentFolders.Add(f);
        }
        RecentFolders.CollectionChanged += (_, _) =>
            OnPropertyChanged(nameof(ShowRecentFolders));
    }

    /// <summary>
    /// Opens a served map URL with the OS default handler — the user's
    /// browser. A test seam in the <see cref="DjiEmbed.Gui.Views.WorkspaceView.WebViewGate"/>
    /// mould, defaulting to the real launch, so headless tests can pin it
    /// and assert the browser-fallback path without spawning anything.
    /// </summary>
    internal Action<string> UrlLauncher { get; set; } = static url =>
        Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });

    /// <summary>Curated option state for the Flight map mode (M3b). Feeds both
    /// the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public FlightMapOptionsViewModel FlightOptions { get; } = new();

    /// <summary>Curated option state for the Photo map mode (M3c). Feeds both
    /// the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public PhotoMapOptionsViewModel PhotoOptions { get; } = new();

    /// <summary>Curated option state for the Embed telemetry mode (M3d). Feeds
    /// both the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public EmbedTelemetryOptionsViewModel EmbedOptions { get; } = new();

    /// <summary>Curated option state for the Convert telemetry mode (M4a). Feeds
    /// both the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public ConvertOptionsViewModel ConvertOptions { get; } = new();

    /// <summary>Curated option state for the Verify mode (M4b). Feeds both
    /// the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>
    /// and the sub-action-shaped <see cref="ActionVerb"/>.</summary>
    public VerifyOptionsViewModel VerifyOptions { get; } = new();

    public IReadOnlyList<WorkspaceMode> Modes => WorkspaceMode.All;

    [ObservableProperty]
    public partial string? SelectedFolder { get; set; }

    [ObservableProperty]
    public partial string? SelectedFile { get; set; }

    /// <summary>The one source chip's text: a folder shows its full path, a
    /// file just its name (the path is long and the name is what identifies
    /// the clip).</summary>
    public string? SourceDisplay =>
        SelectedFolder ?? (SelectedFile is { } f ? Path.GetFileName(f) : null);

    /// <summary>Recent folders that still exist — the hero's quick
    /// re-entry list (M5a), most-recent-first, rebuilt on every push.</summary>
    public ObservableCollection<string> RecentFolders { get; } = [];

    /// <summary>The hero shows recents only while there is nothing else
    /// to look at: no source selected, no run in flight.</summary>
    public bool ShowRecentFolders =>
        RecentFolders.Count > 0 && SourceDisplay is null && !IsBusy;

    /// <summary>Where the folder picker starts: the most recent folder
    /// still on disk, or null for the picker's own default.</summary>
    public string? MostRecentExistingFolder =>
        _stateStore.ExistingRecents().FirstOrDefault();

    [ObservableProperty]
    public partial WorkspaceMode SelectedMode { get; set; } = WorkspaceMode.All[0];

    [ObservableProperty]
    public partial WorkspaceMode? SuggestedMode { get; set; }

    [ObservableProperty]
    public partial bool AllGood { get; set; }

    /// <summary>
    /// True from the first line of a run to its last — including the folder
    /// scan that precedes <see cref="FlowViewModel.Step"/> becoming
    /// <see cref="FlowStep.Running"/> (#340). Everything that feeds a run
    /// (folder, mode, options) freezes on this, so the CLI strip's promise
    /// — what is shown is what runs — holds for the whole run.
    /// </summary>
    [ObservableProperty]
    public partial bool IsBusy { get; private set; }

    partial void OnIsBusyChanged(bool value)
    {
        OpenExistingMapCommand.NotifyCanExecuteChanged();
        OnPropertyChanged(nameof(ShowRecentFolders));
    }

    public ObservableCollection<SetupItem> SetupItems { get; } = [];

    /// <summary>The last Verify run's report rows (M4b), rendered as
    /// cards in the done pane.</summary>
    public ObservableCollection<VerifyCard> VerifyCards { get; } = [];

    [ObservableProperty]
    public partial string? VerifyHeadline { get; set; }

    /// <summary>Maps this folder already had when it was picked (#328) —
    /// what is on disk, independent of the selected mode.</summary>
    public ObservableCollection<ExistingMap> ExistingMaps { get; } = [];

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

    /// <summary>Inline-map pane: a finished run's map, or one the folder
    /// already had and the user asked to see (#328).</summary>
    public bool ShowPreview =>
        PreviewUrl is not null
        && (Step == FlowStep.Done || Step == FlowStep.Pick);

    /// <summary>The hero empty state: idle with nothing to show.</summary>
    public bool ShowIdle => Step == FlowStep.Pick && PreviewUrl is null;

    /// <summary>The three pane gates all derive from Step + PreviewUrl, so
    /// every writer of either has to re-raise all three.</summary>
    private void RaiseGateChanged()
    {
        OnPropertyChanged(nameof(ShowDoneCard));
        OnPropertyChanged(nameof(ShowPreview));
        OnPropertyChanged(nameof(ShowIdle));
    }

    protected override void OnStepChangedCore(FlowStep value)
    {
        RaiseGateChanged();
        OpenExistingMapCommand.NotifyCanExecuteChanged();
    }

    partial void OnPreviewUrlChanged(string? value) => RaiseGateChanged();

    /// <summary>The action button lights up as soon as a run could work.</summary>
    public bool CanRun =>
        SelectedMode.Sources == SourceKinds.None
        || SelectedFolder is not null || SelectedFile is not null;

    /// <summary>Whether the Flight map options panel applies to the current mode.</summary>
    public bool IsFlightMapMode => SelectedMode.Kind == WorkspaceModeKind.FlightMap;

    /// <summary>Whether the Photo map options panel applies to the current mode.</summary>
    public bool IsPhotoMapMode => SelectedMode.Kind == WorkspaceModeKind.PhotoMap;

    /// <summary>Whether the Embed telemetry options panel applies to the current mode.</summary>
    public bool IsEmbedMode => SelectedMode.Kind == WorkspaceModeKind.Embed;

    /// <summary>Whether the Convert telemetry options panel applies to the current mode.</summary>
    public bool IsConvertMode => SelectedMode.Kind == WorkspaceModeKind.Convert;

    /// <summary>Whether the Verify options panel applies to the current mode.</summary>
    public bool IsVerifyMode => SelectedMode.Kind == WorkspaceModeKind.Verify;

    /// <summary>Validate pairing needs a folder — a single file greys its
    /// segment out (the M4b enablement table).</summary>
    public bool VerifyValidateEnabled => SelectedFile is null;

    /// <summary>Sun check needs a single file — a folder greys its
    /// segment out.</summary>
    public bool VerifySunEnabled => SelectedFolder is null;

    /// <summary>The one inline sentence that explains the one greyed
    /// sub-action segment (at most one is ever disabled: a file disables
    /// only Validate, a folder only Sun). Null when nothing is greyed.</summary>
    public string? VerifySubActionNote =>
        SelectedFile is not null
            ? "Validate pairing compares a whole folder of videos with "
              + "their flight logs — choose a folder."
            : SelectedFolder is not null
                ? "Sun check reads one flight log or video — drop a "
                  + "single file."
                : null;

    /// <summary>The action button's verb. Verify is the one mode whose
    /// verb follows a sub-action switch; everywhere else it is the mode's
    /// own.</summary>
    public string ActionVerb =>
        SelectedMode.Kind == WorkspaceModeKind.Verify
            ? VerifyOptions.SubAction switch
            {
                VerifySubAction.Check => "Check metadata",
                VerifySubAction.Validate => "Validate pairing",
                VerifySubAction.Sun => "Check the sun",
                _ => throw new ArgumentOutOfRangeException(
                    nameof(VerifyOptions), VerifyOptions.SubAction, null),
            }
            : SelectedMode.Verb;

    /// <summary>The done card's raw warning list hides while a Verify
    /// report is showing: validate and verify-sun emit their findings
    /// BOTH as warning events and in the summary, and the report is the
    /// curated rendering of the same facts.</summary>
    public bool ShowDoneWarnings =>
        Warnings.Count > 0 && VerifyCards.Count == 0;

    /// <summary>The Save-as override only exists for single-file sources:
    /// the CLI's batch loop writes every output beside its source.</summary>
    public bool ConvertSaveApplies => SelectedFile is not null;

    /// <summary>
    /// True when a Photo map's "Save map to" override would leave the pins
    /// unable to find the original photos. <c>photomap --link-originals</c>
    /// writes each pin's href RELATIVE to the HTML file (the CLI's
    /// <c>--link-base</c> is never passed here, so it defaults to the mapped
    /// folder — see <c>geo/photomap.py</c>'s <c>_link_href</c>), and those
    /// hrefs are what power the embedded 360° panorama viewer (#305). Redirect
    /// the output elsewhere and every "open the original" link 404s, silently.
    /// The fix is not a curated <c>--link-base</c> control — that flag stays
    /// CLI-only by design — it's warning the user before they run. Any
    /// exception from the path APIs (an unparseable path mid-typing) yields
    /// false: a note computation must never throw into a binding.
    /// </summary>
    public bool PhotoLinksCannotReachOriginals
    {
        get
        {
            if (!PhotoOptions.LinkOriginals
                || string.IsNullOrWhiteSpace(PhotoOptions.Output)
                || SelectedFolder is null)
            {
                return false;
            }
            try
            {
                var outputDir = Path.GetDirectoryName(PhotoOptions.Output);
                if (string.IsNullOrEmpty(outputDir))
                {
                    return false;
                }
                var fullOutputDir =
                    Path.TrimEndingDirectorySeparator(Path.GetFullPath(outputDir));
                var fullSourceDir =
                    Path.TrimEndingDirectorySeparator(Path.GetFullPath(SelectedFolder));
                return !string.Equals(fullOutputDir, fullSourceDir,
                    StringComparison.OrdinalIgnoreCase);
            }
            catch (Exception)
            {
                return false;
            }
        }
    }

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
                ?? (SelectedMode.Sources.HasFlag(SourceKinds.Folder) ? "<folder>" : null);
            // folder! is safe in the three explicit arms below: each of those
            // modes has Sources including Folder, so the line above yields the
            // "<folder>" placeholder (never null) when no folder is picked.
            var argv = SelectedMode.Kind switch
            {
                WorkspaceModeKind.FlightMap =>
                    CommandBuilder.FlightMap(folder!, FlightOptions.ToOptions()),
                WorkspaceModeKind.PhotoMap =>
                    CommandBuilder.PhotoMap(folder!, PhotoOptions.ToOptions()),
                WorkspaceModeKind.Embed =>
                    CommandBuilder.Embed(folder!, EmbedOptions.ToOptions()),
                WorkspaceModeKind.Convert =>
                    SelectedFile is { } file
                        ? CommandBuilder.Convert(file, batch: false,
                            ConvertOptions.ToOptions())
                        : CommandBuilder.Convert(folder!, batch: true,
                            ConvertOptions.ToOptions()),
                WorkspaceModeKind.Verify =>
                    CommandBuilder.Verify(
                        SelectedFile ?? SelectedFolder ?? "<source>",
                        VerifyOptions.ToOptions()),
                _ => CommandBuilder.Build(SelectedMode.Kind, folder),
            };
            return CommandLine.Format("dji-embed", argv);
        }
    }

    partial void OnSelectedFolderChanged(string? value)
    {
        if (value is not null)
        {
            SelectedFile = null;
            if (VerifyOptions.SubAction == VerifySubAction.Sun)
            {
                VerifyOptions.SubAction = VerifySubAction.Check;
            }
        }
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        OnPropertyChanged(nameof(PhotoLinksCannotReachOriginals));
        OnPropertyChanged(nameof(SourceDisplay));
        OnPropertyChanged(nameof(ConvertSaveApplies));
        OnPropertyChanged(nameof(VerifyValidateEnabled));
        OnPropertyChanged(nameof(VerifySunEnabled));
        OnPropertyChanged(nameof(VerifySubActionNote));
        OnPropertyChanged(nameof(ShowRecentFolders));
        RunCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedFileChanged(string? value)
    {
        if (value is not null)
        {
            SelectedFolder = null;
            if (VerifyOptions.SubAction == VerifySubAction.Validate)
            {
                // A disabled segment must not stay selected: the strip and
                // the action button would describe a run this source can't
                // feed.
                VerifyOptions.SubAction = VerifySubAction.Check;
            }
        }
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        OnPropertyChanged(nameof(SourceDisplay));
        OnPropertyChanged(nameof(ConvertSaveApplies));
        OnPropertyChanged(nameof(VerifyValidateEnabled));
        OnPropertyChanged(nameof(VerifySunEnabled));
        OnPropertyChanged(nameof(VerifySubActionNote));
        OnPropertyChanged(nameof(ShowRecentFolders));
        RunCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedModeChanged(WorkspaceMode value)
    {
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        OnPropertyChanged(nameof(IsFlightMapMode));
        OnPropertyChanged(nameof(IsPhotoMapMode));
        OnPropertyChanged(nameof(IsEmbedMode));
        OnPropertyChanged(nameof(IsConvertMode));
        OnPropertyChanged(nameof(IsVerifyMode));
        OnPropertyChanged(nameof(ActionVerb));
        RunCommand.NotifyCanExecuteChanged();
    }

    protected override string GenericFailureMessage =>
        SelectedMode.FailureMessage;

    /// <summary>
    /// An absolute output override ("Save map to", "Save copies to")
    /// belongs to the source it was chosen for — carried to a new source it
    /// either overwrites that source's outputs or writes nowhere the new
    /// source shows. Every other option (tile style, privacy, container,
    /// popup fields, title, timezone, ...) is deliberately app-session
    /// state that survives a source change (GUI 2.0 spec).
    ///
    /// A new source (or none) disowns everything derived from the
    /// old one: the previous run's outputs/warnings, per-source output
    /// overrides, the browsed/primed preview. Shared by SetFolderAsync,
    /// SetFile and ClearSource so the three doors stay in step.
    /// </summary>
    private void ResetDerivedSourceState()
    {
        ExistingMaps.Clear();
        Outputs.Clear();
        Warnings.Clear();
        VerifyCards.Clear();
        VerifyHeadline = null;
        FlightOptions.Output = "";
        PhotoOptions.Output = "";
        EmbedOptions.Output = "";
        ConvertOptions.Output = "";
        ResetPreview();
    }

    /// <summary>
    /// Folder drop/pick: remember it, suggest the likely mode. A new folder
    /// is a fresh start — Done/Failed flip back to the idle pane. Ignored
    /// while a run is in flight.
    /// </summary>
    public async Task SetFolderAsync(string folder)
    {
        if (IsBusy)
        {
            return;
        }
        SelectedFolder = folder;
        // One background pass: the classification the mode suggestion needs
        // and the map probe that depends on its timestamps.
        var scan = await Task.Run(() =>
        {
            var contents = _inspectFolder(folder);
            return (contents, maps: ExistingMapFinder.Find(folder, contents));
        });
        // A second pick can land while this scan is in flight; the newest
        // pick owns the state, so a scan that has been overtaken just stops.
        if (SelectedFolder != folder)
        {
            return;
        }
        SuggestedMode =
            scan.contents.HasFlightLogs ? WorkspaceMode.Of(WorkspaceModeKind.FlightMap)
            : scan.contents.HasPhotos ? WorkspaceMode.Of(WorkspaceModeKind.PhotoMap)
            : scan.contents.HasVideos ? WorkspaceMode.Of(WorkspaceModeKind.Embed)
            : null;
        if (SuggestedMode is not null)
        {
            SelectedMode = SuggestedMode;
        }
        // A new folder is a fresh start: the previous run's outputs and
        // warnings must not frame a map that was already sitting here.
        ResetDerivedSourceState();
        foreach (var map in scan.maps)
        {
            ExistingMaps.Add(map);
        }
        Step = FlowStep.Pick;
    }

    /// <summary>
    /// Single-file pick (M4a): the mirror of <see cref="SetFolderAsync"/> for
    /// modes that take one telemetry file. No inspector scan and no
    /// existing-map probe — both are folder concepts — so this is synchronous
    /// and has no overtake race to re-check.
    /// </summary>
    public void SetFile(string path)
    {
        if (IsBusy)
        {
            return;
        }
        SelectedFile = path;
        SuggestedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        SelectedMode = SuggestedMode;
        ResetDerivedSourceState();
        Step = FlowStep.Pick;
    }

    [RelayCommand]
    private void ClearSource()
    {
        // Inert while a run is in flight: pulling the source out from under
        // a running job would also discard the output overrides. IsBusy
        // spans the run's folder scan too, and RunAsync's ownership
        // re-check after the scan stays as defence in depth.
        if (IsBusy)
        {
            return;
        }
        SelectedFolder = null;
        SelectedFile = null;
        SuggestedMode = null;
        ResetDerivedSourceState();
        Step = FlowStep.Pick;
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

    /// <summary>A run started on this folder (M5a MRU signal): push it,
    /// rebuild the pruned display list.</summary>
    private void RememberFolder(string folder)
    {
        _stateStore.PushRecent(folder);
        RecentFolders.Clear();
        foreach (var f in _stateStore.ExistingRecents())
        {
            RecentFolders.Add(f);
        }
        OnPropertyChanged(nameof(MostRecentExistingFolder));
    }

    /// <summary>Hero recents click: identical to dropping the folder.</summary>
    [RelayCommand]
    private Task ChooseRecentAsync(string folder) => SetFolderAsync(folder);

    /// <summary>A run owns the preview pane while it is in flight. Private:
    /// it raises no PropertyChanged, so nothing may bind it — a button gets
    /// this gate from the command's own CanExecute.</summary>
    private bool CanOpenExistingMap => !IsBusy;

    /// <summary>
    /// Show a map the folder already had, in the pane a finished run would
    /// use. Mirrors <see cref="PrimePreviewAsync"/>, except that a preview
    /// which can't render falls back to the browser rather than an
    /// explanatory card: the user asked for this one map, and the browser
    /// answers that ask.
    /// </summary>
    [RelayCommand(CanExecute = nameof(CanOpenExistingMap))]
    private async Task OpenExistingMapAsync(ExistingMap map)
    {
        // Browsing an existing map is real work with the folder (M5a).
        if (SelectedFolder is { } mapFolder)
        {
            RememberFolder(mapFolder);
        }
        if (!_previewAvailable() || CliPath is null)
        {
            // OpenOutputCoreAsync still routes through the map server, so the
            // browser gets an http:// URL and the 360° viewer keeps working.
            await OpenOutputCoreAsync(map.Path);
            return;
        }
        string? url;
        try
        {
            // Browsing isn't part of a flow — nothing cancels it.
            url = await _mapServer.GetUrlAsync(
                CliPath, map.Path, CancellationToken.None);
        }
        // Nothing to cancel back to — any failure, cancellation included,
        // just means "browser instead". (PrimePreviewAsync rethrows
        // OperationCanceledException because it runs inside a flow.)
        catch (Exception)
        {
            url = null;
        }
        if (url is null)
        {
            // base., not the override: the override's first move is another
            // GetUrlAsync, and this one just failed.
            await base.OpenOutputCoreAsync(map.Path);
            return;
        }
        PreviewPath = map.Path;   // path first: the view reads it when the URL lands
        PreviewUrl = url;
    }

    [RelayCommand]
    private void ShowExistingMapInFolder(ExistingMap map) =>
        Reveal.InFolder(map.Path);

    /// <summary>"Process another": back to idle, keep folder and mode.</summary>
    protected override void GoHomeCore()
    {
        ResetPreview();
        // The other door into Pick, where a map the folder already had can
        // render: the finished run's outputs and warnings must not follow it.
        Outputs.Clear();
        Warnings.Clear();
        VerifyCards.Clear();
        VerifyHeadline = null;
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
        // A run starting on a folder is the MRU signal (M5a) — before
        // anything can fail, so guard-blocked runs still count: the user
        // chose to work with this folder. Setup ignores the source and
        // file runs have no folder; neither pushes.
        if (SelectedFile is null && SelectedFolder is { } mruFolder
            && SelectedMode.Kind != WorkspaceModeKind.Setup)
        {
            RememberFolder(mruFolder);
        }
        // Busy for the run's entire lifetime, from before the folder scan:
        // AsyncRelayCommand only covers the button, and Step only turns
        // Running later, inside ExecuteFlowAsync (#340).
        IsBusy = true;
        try
        {
            await RunCoreAsync();
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task RunCoreAsync()
    {
        CliPath ??= _cliResolver?.Invoke();
        if (!EnsureCli())
        {
            return;
        }
        SetupItems.Clear();
        VerifyCards.Clear();
        VerifyHeadline = null;
        AllGood = false;
        // Captured with the folder and options below: SelectedMode is a
        // bare bindable property, so only captures guarantee a mid-scan
        // change cannot pair this run's folder with another mode.
        var mode = SelectedMode;
        if (mode.Kind == WorkspaceModeKind.Setup)
        {
            ResetPreview();
            await RunSetupAsync();
            return;
        }
        // A file in the slot with a folder-only mode selected: say which folder
        // the mode wants instead of failing into the CLI's usage error (#346
        // discipline — reach-aware guidance in the panel's own language).
        if (SelectedFile is not null && !mode.Sources.HasFlag(SourceKinds.File))
        {
            Fail(mode.Kind switch
            {
                WorkspaceModeKind.FlightMap =>
                    "Flight map works on a folder of footage — pick the folder "
                    + "that holds your flights, not a single file.",
                WorkspaceModeKind.PhotoMap =>
                    "Photo map works on a folder of pictures — pick the folder "
                    + "that holds your photos, not a single file.",
                WorkspaceModeKind.Embed =>
                    "Embed telemetry works on a folder of videos with their .SRT "
                    + "flight logs — pick that folder, not a single file.",
                _ => throw new ArgumentOutOfRangeException(nameof(mode), mode.Kind, null),
            });
            return;
        }
        if (mode.Kind == WorkspaceModeKind.Convert && SelectedFile is { } source)
        {
            // No folder, no scan, no overtake window: snapshot and go.
            var single = ConvertOptions.ToOptions();
            ResetPreview();
            await ExecuteFlowAsync(async () =>
                await RunStepAsync("Converting…",
                    CommandBuilder.Convert(source, batch: false, single))
                && await PrimePreviewAsync());
            return;
        }
        if (mode.Kind == WorkspaceModeKind.Verify && SelectedFile is { } vfile)
        {
            var vopts = VerifyOptions.ToOptions();
            // The greyed switch removes shape mismatches, but not this
            // content one: check reads embedded metadata and a .SRT
            // sidecar has none — say so instead of showing three ✗ (#346
            // discipline).
            if (vopts.SubAction == VerifySubAction.Check
                && vfile.EndsWith(".srt", StringComparison.OrdinalIgnoreCase))
            {
                Fail("Check metadata reads the video or photo itself — a "
                     + ".SRT flight log has no embedded metadata to check. "
                     + "Use Sun check for flight logs.");
                return;
            }
            ResetPreview();
            await RunVerifyAsync(vfile, vopts);
            return;
        }
        if (SelectedFolder is not { } folder)
        {
            return;
        }
        // Option snapshots are taken BEFORE the awaited scan: the strip
        // shows this exact command when the button is pressed, and a run
        // owns what it showed — a mid-scan edit must not repair into it.
        var flight = FlightOptions.ToOptions();
        var photo = PhotoOptions.ToOptions();
        var embed = EmbedOptions.ToOptions();
        var convert = ConvertOptions.ToOptions();
        var verify = VerifyOptions.ToOptions();
        var contents = await Task.Run(() => _inspectFolder(folder));
        // The scan runs before ExecuteFlowAsync sets Step = Running, so the
        // folder can be cleared or replaced underneath us while it is in
        // flight. The newest pick owns the state — same rule SetFolderAsync
        // applies to itself — so a run whose folder is gone just stops.
        if (SelectedFolder != folder)
        {
            return;
        }
        // Reset only now, past the awaited scan: clearing the preview any
        // earlier flashes the stale done card while a live map is still up.
        ResetPreview();
        // The scan is recursive, but embed reads one directory level and
        // the map commands recurse only with -r — so each guard asks "is
        // the media where THIS command will look" (#333, #338), and the
        // guidance names the panel's own controls, never the CLI's flags.
        switch (mode.Kind)
        {
            case WorkspaceModeKind.FlightMap
                when !(flight.Recursive
                    ? contents.HasFlightLogs : contents.HasTopLevelFlightLogs):
                Fail(contents.HasFlightLogs
                    ? "Those flight logs are in subfolders — turn on "
                      + "Include subfolders."
                    : "No drone flight logs (.SRT) were found in that "
                      + "folder. Pick the folder that contains your footage"
                      + (flight.Recursive
                          ? " — subfolders are included automatically." : "."));
                return;
            case WorkspaceModeKind.FlightMap:
                await ExecuteFlowAsync(async () =>
                    await RunStepAsync(
                        "Mapping your flights…",
                        CommandBuilder.FlightMap(folder, flight))
                    && await PrimePreviewAsync());
                return;
            case WorkspaceModeKind.PhotoMap
                when !(photo.Recursive
                    ? contents.HasPhotos : contents.HasTopLevelPhotos):
                Fail(contents.HasPhotos
                    ? "Those photos are in subfolders — turn on "
                      + "Include subfolders."
                    : "No photos were found in that folder. Pick the folder "
                      + "that contains your pictures"
                      + (photo.Recursive
                          ? " — subfolders are included automatically." : "."));
                return;
            case WorkspaceModeKind.PhotoMap:
                // --link-originals defaults on: it's what powers the embedded
                // 360° panorama viewer (#305). Its relative hrefs only
                // resolve while the map stays in the photo folder — both are
                // now user choices, and PhotoLinksCannotReachOriginals is
                // what warns before a redirected "Save map to" breaks them.
                await ExecuteFlowAsync(async () =>
                    await RunStepAsync(
                        "Mapping your photos…",
                        CommandBuilder.PhotoMap(folder, photo))
                    && await PrimePreviewAsync());
                return;
            case WorkspaceModeKind.Embed when !contents.HasTopLevelVideos:
                // embed has no recursive form at all, so subfolder-only
                // videos would end as a "Done" card over a zero-file
                // warning run (#338) — say so before spending the run.
                Fail(contents.HasVideos
                    ? "The videos are in subfolders, and Embed reads only "
                      + "the folder you pick — pick the subfolder that "
                      + "holds the videos."
                    : "No videos (.MP4) were found in that folder. Pick the "
                      + "folder that holds the drone videos together with "
                      + "their .SRT flight logs.");
                return;
            case WorkspaceModeKind.Embed:
                await ExecuteFlowAsync(() => RunStepAsync(
                    "Embedding flight data into new copies…",
                    CommandBuilder.Embed(folder, embed)));
                return;
            case WorkspaceModeKind.Convert
                when !(contents.HasTopLevelFlightLogs || contents.HasTopLevelVideos):
                // convert -b globs one directory level (SRT/MP4/MOV) and has no
                // recursive flag at all — same reach rule as embed (#333/#338).
                Fail(contents.HasFlightLogs || contents.HasVideos
                    ? "Those files are in subfolders — Convert reads only the "
                      + "folder you pick. Pick the subfolder that holds the "
                      + "flight logs or videos."
                    : "No flight logs (.SRT) or drone videos were found in "
                      + "that folder. Pick the folder that holds the footage "
                      + "to convert.");
                return;
            case WorkspaceModeKind.Convert:
                await ExecuteFlowAsync(async () =>
                    await RunStepAsync("Converting…",
                        CommandBuilder.Convert(folder, batch: true, convert))
                    && await PrimePreviewAsync());
                return;
            case WorkspaceModeKind.Verify
                when verify.SubAction == VerifySubAction.Check
                     && !(contents.HasTopLevelVideos || contents.HasTopLevelPhotos):
                // check expands one directory level (Task 1) — same reach
                // rule as embed/convert (#333, #338).
                Fail(contents.HasVideos || contents.HasPhotos
                    ? "Those files are in subfolders — Check reads only "
                      + "the folder you pick. Pick the subfolder that "
                      + "holds the videos or photos."
                    : "No videos or photos were found in that folder. "
                      + "Pick the folder that holds the drone footage to "
                      + "check.");
                return;
            case WorkspaceModeKind.Verify
                when verify.SubAction == VerifySubAction.Validate
                     && !contents.HasTopLevelVideos:
                // validate pairs each top-level .MP4 with its .SRT — no
                // top-level videos means a hollow "0 pairs" report.
                Fail(contents.HasVideos
                    ? "Those videos are in subfolders — Validate reads "
                      + "only the folder you pick. Pick the subfolder "
                      + "that holds the videos and their flight logs."
                    : "No videos (.MP4) were found in that folder. "
                      + "Validate pairing needs the folder that holds the "
                      + "videos together with their .SRT flight logs.");
                return;
            case WorkspaceModeKind.Verify:
                // Sun + folder is unreachable: the segment greys out and
                // the selection snaps back to Check on a folder pick.
                await RunVerifyAsync(folder, verify);
                return;
        }
    }

    /// <summary>
    /// One Verify run (M4b): all three sub-commands produce no outputs —
    /// their result summary IS the deliverable, parsed into the report
    /// cards the done pane renders. The RunSetupAsync idiom, not
    /// RunStepAsync: the summary must be read, not just the outputs.
    /// </summary>
    private Task RunVerifyAsync(string source, VerifyTelemetryOptions opts) =>
        ExecuteFlowAsync(async () =>
        {
            var status = opts.SubAction switch
            {
                VerifySubAction.Check => "Checking metadata…",
                VerifySubAction.Validate => "Validating pairs…",
                VerifySubAction.Sun => "Checking the sun…",
                _ => throw new ArgumentOutOfRangeException(
                    nameof(opts), opts.SubAction, null),
            };
            var result = await RunCliAsync(
                status, CommandBuilder.Verify(source, opts));
            if (result.ExitCode != 0
                || result.Terminal is not { Kind: ProgressEventKind.Result } t)
            {
                Fail(result.Terminal?.Message ?? GenericFailureMessage,
                    string.IsNullOrWhiteSpace(result.StderrText)
                        ? null : result.StderrText);
                return false;
            }
            var report = opts.SubAction switch
            {
                VerifySubAction.Check => VerifyReport.FromCheck(t.Summary),
                VerifySubAction.Validate => VerifyReport.FromValidate(t.Summary),
                VerifySubAction.Sun => VerifyReport.FromSun(t.Summary),
                _ => throw new ArgumentOutOfRangeException(
                    nameof(opts), opts.SubAction, null),
            };
            VerifyHeadline = report.Headline;
            foreach (var card in report.Cards)
            {
                VerifyCards.Add(card);
            }
            return true;
        });

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
                UrlLauncher(url);
                return;
            }
        }
        await base.OpenOutputCoreAsync(path);
    }
}
