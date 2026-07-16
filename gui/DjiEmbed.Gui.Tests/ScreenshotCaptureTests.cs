using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;
using Xunit;

namespace DjiEmbed.Gui.Tests;

/// <summary>
/// Opt-in tooling, not a test of behaviour: renders the home screen and writes
/// a PNG to the path in DJIEMBED_CAPTURE_PNG so visual changes can be reviewed
/// without a Windows machine.
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
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var frame = window.CaptureRenderedFrame();
        Assert.NotNull(frame);
        frame!.Save(outPath!, new Avalonia.Media.Imaging.PngBitmapEncoderOptions());
    }
}
