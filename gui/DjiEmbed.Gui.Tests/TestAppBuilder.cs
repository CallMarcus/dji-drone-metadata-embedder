using Avalonia;
using Avalonia.Headless;
using DjiEmbed.Gui;
using DjiEmbed.Gui.Tests;

[assembly: AvaloniaTestApplication(typeof(TestAppBuilder))]

namespace DjiEmbed.Gui.Tests;

public class TestAppBuilder
{
    public static AppBuilder BuildAvaloniaApp() => AppBuilder
        .Configure<App>()
        .UseHeadless(new AvaloniaHeadlessPlatformOptions());
}
