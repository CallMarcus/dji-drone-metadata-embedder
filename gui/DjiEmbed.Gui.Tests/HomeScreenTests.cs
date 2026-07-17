using System.Linq;
using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.VisualTree;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

// The home screen is the anti-bloat contract made testable (design spec
// 2026-07-14, amended by #293): exactly three task cards, one question,
// and a footer link to the CLI discovery screen — no menu bar, no tabs,
// no settings, no fourth card.
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
        // Three cards plus the footer link — nothing else is clickable.
        Assert.Equal(3, buttons.Count(b => b.Classes.Contains("card")));
        Assert.Equal(4, buttons.Count);
        var texts = window.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text).ToList();
        Assert.Contains("Make a map", texts);
        Assert.Contains("Embed telemetry", texts);
        Assert.Contains("Check my setup", texts);
    }

    [AvaloniaFact]
    public void Home_screen_has_cli_escape_hatch_footer_link()
    {
        var window = ShowMainWindow();
        var link = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Classes.Contains("footerLink"));
        var text = string.Join(" ", link.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text ?? ""));
        Assert.Contains("dji-embed", text);
    }

    [AvaloniaFact]
    public void Home_screen_has_the_background_image()
    {
        var window = ShowMainWindow();
        var images = window.GetVisualDescendants().OfType<Image>().ToList();
        Assert.Contains(images, i => i.Source is not null);
    }

    [AvaloniaFact]
    public void Window_title_names_the_product_not_the_assembly()
    {
        var window = ShowMainWindow();
        Assert.Equal("DJI Metadata Embedder", window.Title);
    }
}
