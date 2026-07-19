using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
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
    private static Window ShowWorkspace(WorkspaceViewModel? vm = null)
    {
        // Pin the WebView gate false BEFORE DataContext: assigning the
        // DataContext fires SyncPreview immediately, and this suite must
        // never construct a NativeWebView — its adapter failures surface
        // asynchronously on the dispatcher (GTK on display-less CI), not
        // in any catchable ctor. False makes every attach take the
        // fallback-note path deterministically on every platform.
        var view = new WorkspaceView { WebViewGate = static () => false };
        view.DataContext = vm ?? NewWorkspaceViewModel();
        var window = new Window { Content = view, Width = 1140, Height = 720 };
        window.Show();
        return window;
    }

    private static WorkspaceViewModel NewWorkspaceViewModel() =>
        new("unused", new DjiEmbedRunner(), new FakeMapServer(null), () => { },
            previewAvailable: static () => false);

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

    // Hidden controls stay in the visual tree, so existence checks prove
    // nothing about the IsVisible bindings — these two tests assert
    // IsEffectivelyVisible in both directions instead.
    [AvaloniaFact]
    public void Preview_state_shows_toolbar_and_hides_the_done_card()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.PreviewPath = "flightmap.html";
        vm.PreviewUrl = "http://127.0.0.1:1/flightmap.html";
        vm.Step = FlowStep.Done;
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var buttons = window.GetVisualDescendants().OfType<Button>().ToList();
        Assert.True(buttons.Single(b => b.Name == "OpenInBrowserButton")
            .IsEffectivelyVisible);
        Assert.True(buttons.Single(b => b.Name == "ShowInFolderButton")
            .IsEffectivelyVisible);
        Assert.True(window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "PreviewHost").IsEffectivelyVisible);
        Assert.False(window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Text == "✅ Done").IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public void Setting_a_preview_url_never_crashes_a_machine_without_webview()
    {
        // The gate is pinned false (see ShowWorkspace): a machine without a
        // usable web engine must degrade to the in-pane note — never throw,
        // never even construct the control — and the note must actually be
        // visible; that is the machine-without-webview UX promise.
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.PreviewPath = "flightmap.html";
        vm.PreviewUrl = "http://127.0.0.1:1/flightmap.html";
        vm.Step = FlowStep.Done;
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var host = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "PreviewHost");
        var note = Assert.IsType<TextBlock>(host.Child);   // fallback note, not a WebView
        Assert.True(note.IsEffectivelyVisible);
        vm.GoHomeCommand.Execute(null);
        Dispatcher.UIThread.RunJobs();
        Assert.Null(host.Child);               // leaving Done detaches whatever was there
        vm.PreviewUrl = "http://127.0.0.1:1/again.html";
        Dispatcher.UIThread.RunJobs();
        Assert.NotNull(host.Child);            // and a second run re-attaches
    }

    [AvaloniaFact]
    public void Recreated_view_syncs_an_already_live_preview()
    {
        // The VM outlives the view: ViewLocator rebuilds the workspace view
        // on every CurrentPage flip (footer link → CLI discovery → back), so
        // a fresh view must adopt a preview that is already showing.
        var vm = NewWorkspaceViewModel();
        vm.PreviewPath = "flightmap.html";
        vm.PreviewUrl = "http://127.0.0.1:1/flightmap.html";
        vm.Step = FlowStep.Done;
        var window = ShowWorkspace(vm);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var host = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "PreviewHost");
        Assert.NotNull(host.Child);
    }

    [AvaloniaFact]
    public void Degraded_done_card_carries_the_calm_webview_note()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.PreviewUnavailable = true;
        vm.Step = FlowStep.Done;
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var tip = window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => (t.Text ?? "").Contains("WebView2"));
        Assert.True(tip.IsEffectivelyVisible);

        vm.PreviewUnavailable = false;   // a healthy Done never shows the tip
        Dispatcher.UIThread.RunJobs();
        Assert.False(tip.IsEffectivelyVisible);
    }
}
