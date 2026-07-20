using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
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
        PhotoOptions.PropertyChanged += (_, _) =>
        {
            OnPropertyChanged(nameof(CommandPreview));
            OnPropertyChanged(nameof(PhotoLinksCannotReachOriginals));
        };
        EmbedOptions.PropertyChanged += (_, _) =>
            OnPropertyChanged(nameof(CommandPreview));
    }

    /// <summary>Curated option state for the Flight map mode (M3b). Feeds both
    /// the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public FlightMapOptionsViewModel FlightOptions { get; } = new();

    /// <summary>Curated option state for the Photo map mode (M3c). Feeds both
    /// the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public PhotoMapOptionsViewModel PhotoOptions { get; } = new();

    /// <summary>Curated option state for the Embed telemetry mode (M3d). Feeds
    /// both the run and the CLI strip; any change re-raises <see cref="CommandPreview"/>.</summary>
    public EmbedTelemetryOptionsViewModel EmbedOptions { get; } = new();

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
    public bool CanRun => !SelectedMode.NeedsFolder || SelectedFolder is not null;

    /// <summary>Whether the Flight map options panel applies to the current mode.</summary>
    public bool IsFlightMapMode => SelectedMode.Kind == WorkspaceModeKind.FlightMap;

    /// <summary>Whether the Photo map options panel applies to the current mode.</summary>
    public bool IsPhotoMapMode => SelectedMode.Kind == WorkspaceModeKind.PhotoMap;

    /// <summary>Whether the Embed telemetry options panel applies to the current mode.</summary>
    public bool IsEmbedMode => SelectedMode.Kind == WorkspaceModeKind.Embed;

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
                ?? (SelectedMode.NeedsFolder ? "<folder>" : null);
            // folder! is safe in the three explicit arms below: each of those
            // modes has NeedsFolder true, so the line above yields the
            // "<folder>" placeholder (never null) when no folder is picked.
            var argv = SelectedMode.Kind switch
            {
                WorkspaceModeKind.FlightMap =>
                    CommandBuilder.FlightMap(folder!, FlightOptions.ToOptions()),
                WorkspaceModeKind.PhotoMap =>
                    CommandBuilder.PhotoMap(folder!, PhotoOptions.ToOptions()),
                WorkspaceModeKind.Embed =>
                    CommandBuilder.Embed(folder!, EmbedOptions.ToOptions()),
                _ => CommandBuilder.Build(SelectedMode.Kind, folder),
            };
            return CommandLine.Format("dji-embed", argv);
        }
    }

    partial void OnSelectedFolderChanged(string? value)
    {
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        OnPropertyChanged(nameof(PhotoLinksCannotReachOriginals));
        RunCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedModeChanged(WorkspaceMode value)
    {
        OnPropertyChanged(nameof(CanRun));
        OnPropertyChanged(nameof(CommandPreview));
        OnPropertyChanged(nameof(IsFlightMapMode));
        OnPropertyChanged(nameof(IsPhotoMapMode));
        OnPropertyChanged(nameof(IsEmbedMode));
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
        // One background pass: the classification the mode suggestion needs
        // and the map probe that depends on its timestamps.
        var scan = await Task.Run(() =>
        {
            var contents = FolderInspector.Inspect(folder);
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
        ExistingMaps.Clear();
        foreach (var map in scan.maps)
        {
            ExistingMaps.Add(map);
        }
        // A new folder is a fresh start: the previous run's outputs and
        // warnings must not frame a map that was already sitting here.
        Outputs.Clear();
        Warnings.Clear();
        // An absolute output override ("Save map to", "Save copies to")
        // belongs to the folder it was chosen for — carried to a new folder it
        // either overwrites that folder's outputs or writes nowhere the new
        // folder shows. Every other option (tile style, privacy, container,
        // popup fields, title, timezone, ...) is deliberately app-session
        // state that survives a folder change (GUI 2.0 spec).
        FlightOptions.Output = "";
        PhotoOptions.Output = "";
        EmbedOptions.Output = "";
        ResetPreview();
        Step = FlowStep.Pick;
    }

    [RelayCommand]
    private void ClearFolder()
    {
        // Inert mid-run, exactly as SetFolderAsync is: pulling the folder out
        // from under a running job would also discard the output overrides.
        if (Step == FlowStep.Running)
        {
            return;
        }
        SelectedFolder = null;
        SuggestedMode = null;
        ExistingMaps.Clear();
        // The same ownership rule SetFolderAsync explains: an output override
        // belongs to the folder it was chosen for, and removing the folder
        // leaves it with no owner at all. The strip is where that shows —
        // it would go on advertising `--output <path>` beside the `<folder>`
        // placeholder. (Each Output setter raises through the ctor's options
        // subscription, so the strip repaints with the cleared value. The
        // SelectedFolder raise above fires before these lines and still sees
        // the old path.)
        FlightOptions.Output = "";
        PhotoOptions.Output = "";
        EmbedOptions.Output = "";
        // A map browsed out of that folder can't outlive it: without this the
        // pane keeps rendering it with no folder and no drop hero behind it.
        ResetPreview();
        // Nor can a finished run's results: without these, ✕ after a run left
        // Step == Done with the preview nulled, which is precisely the
        // done-card state — outputs and warnings listed over no folder.
        Outputs.Clear();
        Warnings.Clear();
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

    /// <summary>A run owns the preview pane while it is in flight. Private:
    /// it raises no PropertyChanged, so nothing may bind it — a button gets
    /// this gate from the command's own CanExecute.</summary>
    private bool CanOpenExistingMap => Step != FlowStep.Running;

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
                // --link-originals defaults on: it's what powers the embedded
                // 360° panorama viewer (#305). Its relative hrefs only
                // resolve while the map stays in the photo folder — both are
                // now user choices, and PhotoLinksCannotReachOriginals is
                // what warns before a redirected "Save map to" breaks them.
                await ExecuteFlowAsync(async () =>
                    await RunStepAsync(
                        "Mapping your photos…",
                        CommandBuilder.PhotoMap(folder, PhotoOptions.ToOptions()))
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
                    CommandBuilder.Embed(folder, EmbedOptions.ToOptions())));
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
