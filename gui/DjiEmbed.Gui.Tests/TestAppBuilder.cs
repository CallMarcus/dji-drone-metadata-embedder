using Avalonia;
using Avalonia.Headless;
using DjiEmbed.Gui;
using DjiEmbed.Gui.Tests;

[assembly: AvaloniaTestApplication(typeof(TestAppBuilder))]

namespace DjiEmbed.Gui.Tests;

public class TestAppBuilder
{
    // Skia-backed headless drawing so tests can capture real rendered frames
    // (screenshots for design review); input/lifetime behaviour is unchanged.
    public static AppBuilder BuildAvaloniaApp() => AppBuilder
        .Configure<App>()
        .UseSkia()
        .UseHeadless(new AvaloniaHeadlessPlatformOptions { UseHeadlessDrawing = false });
}
