using System.Linq;
using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.VisualTree;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

// The home screen is the anti-bloat contract made testable (design spec
// 2026-07-14): exactly three task cards, one question, a CLI escape-hatch
// footer — no menu bar, no tabs, no settings.
public class HomeScreenTests
{
    private static MainWindow ShowMainWindow()
    {
        var window = new MainWindow { DataContext = new MainViewModel() };
        window.Show();
        return window;
    }

    [AvaloniaFact]
    public void Home_screen_asks_the_question()
    {
        var window = ShowMainWindow();
        var texts = window.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text).ToList();
        Assert.Contains("What do you want to do?", texts);
    }

    [AvaloniaFact]
    public void Home_screen_shows_exactly_three_task_cards()
    {
        var window = ShowMainWindow();
        var buttons = window.GetVisualDescendants().OfType<Button>().ToList();
        Assert.Equal(3, buttons.Count);
        var texts = window.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text).ToList();
        Assert.Contains("Make a map", texts);
        Assert.Contains("Embed telemetry", texts);
        Assert.Contains("Check my setup", texts);
    }

    [AvaloniaFact]
    public void Home_screen_has_cli_escape_hatch_footer()
    {
        var window = ShowMainWindow();
        var texts = window.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text ?? "").ToList();
        Assert.Contains(texts, t => t.Contains("dji-embed"));
    }

    [AvaloniaFact]
    public void Window_title_names_the_product_not_the_assembly()
    {
        var window = ShowMainWindow();
        Assert.Equal("DJI Metadata Embedder", window.Title);
    }
}
