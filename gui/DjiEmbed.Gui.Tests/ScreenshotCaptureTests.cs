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

        var makeMap = new MakeMapViewModel(null, new DjiEmbedRunner(), new MapServer(), NoOp());
        CaptureView(new MakeMapView { DataContext = makeMap },
            Png("makemap-pick"));

        makeMap.Step = FlowStep.Done;
        makeMap.Outputs.Add(@"C:\Users\demo\Videos\flight\photo_map.html");
        makeMap.Outputs.Add(@"C:\Users\demo\Videos\flight\flight_map.html");
        CaptureView(new MakeMapView { DataContext = makeMap },
            Png("makemap-done"));

        var embed = new EmbedTelemetryViewModel(
            null, new DjiEmbedRunner(), NoOp());
        CaptureView(new EmbedTelemetryView { DataContext = embed },
            Png("embed-pick"));

        var dragged = new EmbedTelemetryView { DataContext = embed };
        FolderPicking.SetDragOver(dragged.FindControl<Border>("DropZone")!, true);
        CaptureView(dragged, Png("embed-pick-dragover"));

        embed.Step = FlowStep.Running;
        embed.StatusText = "Embedding your flight data…";
        embed.CurrentItem = "DJI_0042.MP4";
        embed.Current = 3;
        embed.Total = 12;
        CaptureView(new EmbedTelemetryView { DataContext = embed },
            Png("embed-running"));

        embed.Step = FlowStep.Done;
        embed.Outputs.Add(@"C:\Users\demo\Videos\flight\processed");
        embed.Warnings.Add("DJI_0007.MP4: skipped — no matching .SRT flight log");
        CaptureView(new EmbedTelemetryView { DataContext = embed },
            Png("embed-done"));

        embed.Step = FlowStep.Failed;
        embed.ErrorMessage = "Something went wrong while embedding the "
            + "flight data. Your original videos were not changed.";
        embed.ErrorDetails = string.Join('\n',
            Enumerable.Range(1, 30).Select(i => $"ffmpeg: pass {i} …"))
            + "\nTraceback (most recent call last):\n"
            + "  File \"processor.py\", line 214, in embed\n"
            + "RuntimeError: ffmpeg exited with code 1";
        CaptureView(new EmbedTelemetryView { DataContext = embed },
            Png("embed-failed"));

        var failedOpen = new EmbedTelemetryView { DataContext = embed };
        var failedWindow = new Window
        {
            Width = 560, Height = 520, Content = failedOpen,
        };
        failedWindow.Show();
        Dispatcher.UIThread.RunJobs();
        foreach (var expander in failedWindow.GetVisualDescendants()
                     .OfType<Expander>().ToList())
        {
            expander.IsExpanded = true;
        }
        Capture(failedWindow, Png("embed-failed-details"));

        var discovery = new CliDiscoveryViewModel(null, NoOp());
        CaptureView(new CliDiscoveryView { DataContext = discovery },
            Png("cli-discovery"));

        var setup = new CheckSetupViewModel(null, new DjiEmbedRunner(), NoOp());
        setup.Step = FlowStep.Done;
        setup.AllGood = true;
        setup.Items.Add(new SetupItem(
            "Video tools (FFmpeg)", true, "version 7.1"));
        setup.Items.Add(new SetupItem(
            "Photo tools (ExifTool)", true, "version 13.29"));
        CaptureView(new CheckSetupView { DataContext = setup },
            Png("checksetup-done"));
    }

    private static void CaptureView(Control view, string outPath) =>
        Capture(new Window { Width = 560, Height = 520, Content = view },
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
