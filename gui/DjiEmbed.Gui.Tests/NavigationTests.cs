using System.Linq;
using Avalonia.Controls;
using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.VisualTree;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

public class NavigationTests
{
    [AvaloniaFact]
    public void Make_a_map_card_navigates_to_the_map_flow()
    {
        var window = new MainWindow { DataContext = new MainViewModel() };
        window.Show();

        var makeMap = window.GetVisualDescendants().OfType<Button>()
            .First(b => b.GetVisualDescendants().OfType<TextBlock>()
                .Any(t => t.Text == "Make a map"));
        makeMap.Focus();
        window.KeyPressQwerty(Avalonia.Input.PhysicalKey.Enter,
            Avalonia.Input.RawInputModifiers.None);

        Assert.NotNull(window.GetVisualDescendants()
            .OfType<MakeMapView>().FirstOrDefault());
    }

    [AvaloniaFact]
    public void Embed_card_navigates_to_the_embed_flow()
    {
        var main = new MainViewModel();
        var window = new MainWindow { DataContext = main };
        window.Show();
        main.StartTask(TaskKind.EmbedTelemetry);
        Avalonia.Threading.Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        Assert.IsType<EmbedTelemetryViewModel>(main.CurrentPage);
        Assert.NotNull(window.GetVisualDescendants()
            .OfType<EmbedTelemetryView>().FirstOrDefault());
    }

    [AvaloniaFact]
    public void Check_setup_view_resolves_and_autostarts()
    {
        // A null CLI path makes autostart fail fast without spawning
        // anything — proving the Loaded wiring fired.
        var vm = new CheckSetupViewModel(
            null, new Services.DjiEmbedRunner(), () => { });
        var window = new MainWindow { DataContext = new MainViewModel() };
        window.Show();
        ((MainViewModel)window.DataContext!).CurrentPage = vm;
        Avalonia.Threading.Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        Assert.NotNull(window.GetVisualDescendants()
            .OfType<CheckSetupView>().FirstOrDefault());
        Assert.Equal(FlowStep.Failed, vm.Step);
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

    [AvaloniaFact]
    public void Cli_discovery_back_button_returns_home()
    {
        var main = new MainViewModel();
        var window = new MainWindow { DataContext = main };
        window.Show();
        main.StartTask(TaskKind.CliDiscovery);

        var vm = Assert.IsType<CliDiscoveryViewModel>(main.CurrentPage);
        vm.GoHomeCommand.Execute(null);
        Assert.IsType<HomeViewModel>(main.CurrentPage);
    }

    [AvaloniaFact]
    public void Map_flow_back_button_returns_home()
    {
        var main = new MainViewModel();
        var window = new MainWindow { DataContext = main };
        window.Show();
        main.StartTask(TaskKind.MakeMap);

        var vm = Assert.IsType<MakeMapViewModel>(main.CurrentPage);
        vm.GoHomeCommand.Execute(null);
        Assert.IsType<HomeViewModel>(main.CurrentPage);
    }

    [AvaloniaFact]
    public void Map_flow_pick_step_offers_drop_and_browse()
    {
        var main = new MainViewModel();
        var window = new MainWindow { DataContext = main };
        window.Show();
        main.StartTask(TaskKind.MakeMap);
        // Give the ContentControl a layout pass so the new page's visual
        // tree exists before we inspect it.
        Avalonia.Threading.Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var texts = window.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text ?? "").ToList();
        Assert.Contains(texts, t => t.Contains("Drop a folder"));
        Assert.Contains(texts, t => t.Contains("Choose a folder"));
    }
}
