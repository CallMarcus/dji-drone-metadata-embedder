using System.Linq;
using Avalonia.Controls;
using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.VisualTree;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

// GUI 2.0: the workspace IS the app. The only other page is the read-only
// CLI discovery screen, reached from the workspace footer; coming back
// returns the same long-lived workspace instance (state preserved).
public class NavigationTests
{
    [Fact]
    public void Root_page_is_the_workspace()
    {
        Assert.IsType<WorkspaceViewModel>(new MainViewModel().CurrentPage);
    }

    [Fact]
    public void Cli_discovery_round_trip_preserves_the_workspace_instance()
    {
        var main = new MainViewModel();
        var workspace = Assert.IsType<WorkspaceViewModel>(main.CurrentPage);
        workspace.OpenCliDiscoveryCommand.Execute(null);
        var discovery = Assert.IsType<CliDiscoveryViewModel>(main.CurrentPage);
        discovery.GoHomeCommand.Execute(null);
        Assert.Same(workspace, main.CurrentPage);

        // Opening discovery again must not hand back the same instance —
        // it's a fresh, disposable page each time, unlike the workspace.
        workspace.OpenCliDiscoveryCommand.Execute(null);
        var discoveryAgain = Assert.IsType<CliDiscoveryViewModel>(main.CurrentPage);
        Assert.NotSame(discovery, discoveryAgain);
    }

    [AvaloniaFact]
    public void Footer_link_navigates_to_the_cli_discovery_screen()
    {
        var window = new MainWindow { DataContext = new MainViewModel() };
        window.Show();

        var link = window.GetVisualDescendants().OfType<Button>()
            .First(b => b.Classes.Contains("footerLink"));
        link.Focus();
        window.KeyPressQwerty(Avalonia.Input.PhysicalKey.Enter,
            Avalonia.Input.RawInputModifiers.None);

        Assert.NotNull(window.GetVisualDescendants()
            .OfType<CliDiscoveryView>().FirstOrDefault());
    }
}
