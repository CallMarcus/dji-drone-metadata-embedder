using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

// The workspace screen is the GUI 2.0 contract made testable (spec
// 2026-07-18): one window, four modes in the strip, a drop-zone hero,
// a CLI footer link — no menu bar, no tabs, no settings.
public class WorkspaceScreenTests
{
    private static Window ShowWorkspace()
    {
        var view = new WorkspaceView
        {
            DataContext = new WorkspaceViewModel(
                "unused", new DjiEmbedRunner(), new FakeMapServer(null), () => { },
                previewAvailable: static () => false),
        };
        var window = new Window { Content = view, Width = 1140, Height = 720 };
        window.Show();
        return window;
    }

    [AvaloniaFact]
    public void Mode_strip_shows_exactly_the_four_m1_modes()
    {
        var window = ShowWorkspace();
        var strip = window.GetVisualDescendants().OfType<ListBox>()
            .Single(l => l.Name == "ModeStrip");
        Assert.Equal(4, strip.ItemCount);
    }

    [AvaloniaFact]
    public void Source_zone_has_drop_zone_and_choose_button()
    {
        var window = ShowWorkspace();
        Assert.Single(window.GetVisualDescendants().OfType<Border>(),
            b => b.Name == "DropZone");
        Assert.Single(window.GetVisualDescendants().OfType<Button>(),
            b => b.Name == "ChooseFolderButton");
    }

    [AvaloniaFact]
    public void Action_button_carries_the_selected_modes_verb()
    {
        var window = ShowWorkspace();
        var texts = window.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text).ToList();
        Assert.Contains("Generate flight map", texts);
    }

    [AvaloniaFact]
    public void Cli_escape_hatch_footer_link_survives()
    {
        var window = ShowWorkspace();
        var link = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Classes.Contains("footerLink"));
        var text = string.Join(" ", link.GetVisualDescendants()
            .OfType<TextBlock>().Select(t => t.Text ?? ""));
        Assert.Contains("dji-embed", text);
    }

    [AvaloniaFact]
    public void Idle_pane_keeps_the_photo_identity()
    {
        var window = ShowWorkspace();
        var images = window.GetVisualDescendants().OfType<Image>().ToList();
        Assert.Contains(images, i => i.Source is not null);
    }

    [AvaloniaFact]
    public void Preview_state_shows_toolbar_and_hides_the_done_card()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.PreviewPath = "flightmap.html";
        vm.PreviewUrl = "http://127.0.0.1:1/flightmap.html";
        vm.Step = FlowStep.Done;
        var buttons = window.GetVisualDescendants().OfType<Button>().ToList();
        Assert.Single(buttons, b => b.Name == "OpenInBrowserButton");
        Assert.Single(buttons, b => b.Name == "ShowInFolderButton");
        Assert.Single(window.GetVisualDescendants().OfType<Border>(),
            b => b.Name == "PreviewHost");
        Assert.True(vm.ShowPreview);
        Assert.False(vm.ShowDoneCard);
    }

    [AvaloniaFact]
    public void Degraded_done_card_carries_the_calm_webview_note()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.PreviewUnavailable = true;
        vm.Step = FlowStep.Done;
        var texts = window.GetVisualDescendants().OfType<TextBlock>()
            .Select(t => t.Text ?? "").ToList();
        Assert.Contains(texts, t => t.Contains("WebView2"));
    }
}
