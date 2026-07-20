using Avalonia.Controls;
using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;
using Xunit;

namespace DjiEmbed.Gui.Tests;

/// <summary>
/// Opt-in tooling, not a test of behaviour: renders the app's screens and
/// writes PNGs so visual changes can be reviewed without a Windows machine.
/// </summary>
public class ScreenshotCaptureTests
{
    [AvaloniaFact]
    public void Captures_home_screen_to_png_when_requested()
    {
        var outPath = Environment.GetEnvironmentVariable("DJIEMBED_CAPTURE_PNG");
        Assert.SkipWhen(string.IsNullOrEmpty(outPath),
            "Set DJIEMBED_CAPTURE_PNG=<path.png> to capture the home screen.");

        var window = new MainWindow { DataContext = new MainViewModel() };
        Capture(window, outPath!);
    }

    /// <summary>
    /// Renders every view in every flow step with representative fake data
    /// and writes one PNG per screen into DJIEMBED_CAPTURE_DIR.
    /// </summary>
    [AvaloniaFact]
    public void Captures_every_screen_to_dir_when_requested()
    {
        var dir = Environment.GetEnvironmentVariable("DJIEMBED_CAPTURE_DIR");
        Assert.SkipWhen(string.IsNullOrEmpty(dir),
            "Set DJIEMBED_CAPTURE_DIR=<dir> to capture all screens.");
        Directory.CreateDirectory(dir!);

        string Png(string name) => Path.Combine(dir!, name + ".png");
        static Action NoOp() => () => { };

        Capture(new MainWindow { DataContext = new MainViewModel() },
            Png("home"));

        var workspace = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new FakeMapServer(null), NoOp(),
            previewAvailable: static () => false);
        CaptureView(new WorkspaceView { DataContext = workspace },
            Png("workspace-pick"));

        var dragged = new WorkspaceView { DataContext = workspace };
        FolderPicking.SetDragOver(dragged.FindControl<Border>("DropZone")!, true);
        CaptureView(dragged, Png("workspace-pick-dragover"));

        workspace.Step = FlowStep.Running;
        workspace.StatusText = "Embedding your flight data…";
        workspace.CurrentItem = "DJI_0042.MP4";
        workspace.Current = 3;
        workspace.Total = 12;
        CaptureView(new WorkspaceView { DataContext = workspace },
            Png("workspace-running"));

        workspace.Step = FlowStep.Done;
        workspace.Outputs.Add(@"C:\Users\demo\Videos\flight\photo_map.html");
        workspace.Outputs.Add(@"C:\Users\demo\Videos\flight\flight_map.html");
        workspace.Warnings.Add("DJI_0007.MP4: skipped — no matching .SRT flight log");
        CaptureView(new WorkspaceView { DataContext = workspace },
            Png("workspace-done"));

        var setupDone = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new FakeMapServer(null), NoOp(),
            previewAvailable: static () => false);
        setupDone.Step = FlowStep.Done;
        setupDone.AllGood = true;
        setupDone.SetupItems.Add(new SetupItem(
            "Video tools (FFmpeg)", true, "version 7.1"));
        setupDone.SetupItems.Add(new SetupItem(
            "Photo tools (ExifTool)", true, "version 13.29"));
        CaptureView(new WorkspaceView { DataContext = setupDone },
            Png("workspace-setup-done"));

        var failed = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new FakeMapServer(null), NoOp(),
            previewAvailable: static () => false);
        failed.Step = FlowStep.Failed;
        failed.ErrorMessage = "Something went wrong while embedding the "
            + "flight data. Your original videos were not changed.";
        failed.ErrorDetails = string.Join('\n',
            Enumerable.Range(1, 30).Select(i => $"ffmpeg: pass {i} …"))
            + "\nTraceback (most recent call last):\n"
            + "  File \"processor.py\", line 214, in embed\n"
            + "RuntimeError: ffmpeg exited with code 1";
        CaptureView(new WorkspaceView { DataContext = failed },
            Png("workspace-failed"));

        var failedOpen = new WorkspaceView { DataContext = failed };
        var failedWindow = new Window
        {
            Width = 1140, Height = 720, Content = failedOpen,
        };
        failedWindow.Show();
        Dispatcher.UIThread.RunJobs();
        foreach (var expander in failedWindow.GetVisualDescendants()
                     .OfType<Expander>().ToList())
        {
            expander.IsExpanded = true;
        }
        Capture(failedWindow, Png("workspace-failed-details"));

        var discovery = new CliDiscoveryViewModel(null, NoOp());
        CaptureView(new CliDiscoveryView { DataContext = discovery },
            Png("cli-discovery"), width: 560, height: 520);
    }

    /// <summary>
    /// Done step with an inline map preview: toolbar plus the preview
    /// inset. The view's WebView gate is pinned false, so the pane shows
    /// the calm fallback note instead of a NativeWebView — deterministic
    /// on every host (constructing the control headlessly would fail
    /// asynchronously on display-less CI), and better for layout review
    /// than the blank pane it used to render. Deliberately a separate
    /// method rather than part of
    /// Captures_every_screen_to_dir_when_requested: this one exercises
    /// the attach path, and that is kept isolated from the main matrix
    /// run — don't merge them.
    /// </summary>
    [AvaloniaFact]
    public void Captures_preview_state_to_dir_when_requested()
    {
        var dir = Environment.GetEnvironmentVariable("DJIEMBED_CAPTURE_DIR");
        Assert.SkipWhen(string.IsNullOrEmpty(dir),
            "Set DJIEMBED_CAPTURE_DIR=<dir> to capture the preview state.");
        Directory.CreateDirectory(dir!);

        var vm = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new FakeMapServer(null), () => { },
            previewAvailable: static () => false);
        // Forward slashes, unlike the other fake paths: the toolbar shows
        // Path.GetFileName(PreviewPath), and on the Linux capture host
        // that only splits on '/' — backslashes would render whole.
        vm.PreviewPath = "C:/Users/demo/Videos/flight/flight_map.html";
        vm.PreviewUrl = "http://127.0.0.1:1/flight_map.html";
        vm.Step = FlowStep.Done;
        // Gate before DataContext: assigning the DataContext fires
        // SyncPreview immediately, which would otherwise probe for real.
        var view = new WorkspaceView { WebViewGate = static () => false };
        view.DataContext = vm;
        CaptureView(view, Path.Combine(dir!, "workspace-preview.png"));
    }

    /// <summary>
    /// Done step on a machine without a usable WebView2: the done card
    /// with the WebView2-unavailable note visible instead of the inline
    /// map, above the output row whose Open button the note points at.
    /// </summary>
    [AvaloniaFact]
    public void Captures_degraded_done_state_to_dir_when_requested()
    {
        var dir = Environment.GetEnvironmentVariable("DJIEMBED_CAPTURE_DIR");
        Assert.SkipWhen(string.IsNullOrEmpty(dir),
            "Set DJIEMBED_CAPTURE_DIR=<dir> to capture the degraded state.");
        Directory.CreateDirectory(dir!);

        var vm = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new FakeMapServer(null), () => { },
            previewAvailable: static () => false);
        vm.Outputs.Add(@"C:\Users\demo\Videos\flight\flight_map.html");
        vm.PreviewUnavailable = true;
        vm.Step = FlowStep.Done;
        // No PreviewUrl is set, so nothing attaches — but pin the gate
        // anyway so this capture can never construct a WebView on any host.
        var view = new WorkspaceView { WebViewGate = static () => false };
        view.DataContext = vm;
        CaptureView(view,
            Path.Combine(dir!, "workspace-done-degraded.png"));
    }

    /// <summary>
    /// Pick step on a folder an earlier run already mapped: the
    /// "Already in this folder" zone at its tallest — both map kinds, one
    /// of them stale — so the left column's fold can be reviewed in the
    /// exact case that inserts it above OPTIONS.
    /// </summary>
    [AvaloniaFact]
    public void Captures_existing_maps_panel_to_dir_when_requested()
    {
        var dir = Environment.GetEnvironmentVariable("DJIEMBED_CAPTURE_DIR");
        Assert.SkipWhen(string.IsNullOrEmpty(dir),
            "Set DJIEMBED_CAPTURE_DIR=<dir> to capture the existing-maps panel.");
        Directory.CreateDirectory(dir!);

        var vm = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new FakeMapServer(null), () => { },
            previewAvailable: static () => false);
        vm.SelectedFolder = @"C:\Users\demo\Videos\flight";
        vm.ExistingMaps.Add(new ExistingMap(
            @"C:\Users\demo\Videos\flight\flightmap.html", "Flight map",
            DateTime.UtcNow.AddDays(-2), Stale: true));
        vm.ExistingMaps.Add(new ExistingMap(
            @"C:\Users\demo\Videos\flight\photomap.html", "Photo map",
            DateTime.UtcNow.AddHours(-3), Stale: false));
        var view = new WorkspaceView { WebViewGate = static () => false };
        view.DataContext = vm;
        CaptureView(view, Path.Combine(dir!, "workspace-existing-maps.png"));
    }

    private static void CaptureView(
        Control view, string outPath, double width = 1140, double height = 720) =>
        Capture(new Window { Width = width, Height = height, Content = view },
            outPath);

    private static void Capture(Window window, string outPath)
    {
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var frame = window.CaptureRenderedFrame();
        Assert.NotNull(frame);
        frame!.Save(outPath, new Avalonia.Media.Imaging.PngBitmapEncoderOptions());
        window.Close();
    }
}
