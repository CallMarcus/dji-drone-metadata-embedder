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

    [AvaloniaFact]
    public void Cli_transparency_strip_shows_the_live_command()
    {
        var window = ShowWorkspace();   // default mode Flight map, no folder
        var strip = window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Name == "CommandPreviewText");
        Assert.Contains("dji-embed flightmap", strip.Text);
        Assert.Contains("<folder>", strip.Text);          // no folder picked yet
        Assert.DoesNotContain("--progress", strip.Text);  // teaching form, not the machine flag
        Assert.Single(window.GetVisualDescendants().OfType<Button>(),
            b => b.Name == "CopyCommandButton");
    }

    // M3b: the Flight map options panel renders only for Flight map, with the
    // Advanced expander closed by default.
    [AvaloniaFact]
    public void Flight_map_mode_shows_the_options_panel_with_advanced_collapsed()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "FlightOptionsPanel");
        Assert.True(panel.IsEffectivelyVisible);
        var advanced = window.GetVisualDescendants().OfType<Expander>()
            .Single(e => e.Name == "FlightAdvanced");
        Assert.False(advanced.IsExpanded);
    }

    [AvaloniaFact]
    public void Non_flight_map_mode_hides_the_options_panel()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "FlightOptionsPanel");
        Assert.False(panel.IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public async Task A_folder_with_an_existing_map_shows_the_already_here_panel()
    {
        var dir = Directory.CreateTempSubdirectory("djiembed-screen-maps").FullName;
        try
        {
            File.WriteAllText(Path.Combine(dir, "DJI_0001.SRT"), "");
            File.WriteAllText(Path.Combine(dir, "flightmap.html"), "");
            var window = ShowWorkspace();
            var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;

            await vm.SetFolderAsync(dir);
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();

            var panel = window.GetVisualDescendants().OfType<Border>()
                .Single(b => b.Name == "ExistingMapsPanel");
            Assert.True(panel.IsEffectivelyVisible);
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    // A state transition, not a fresh window: asserting "hidden" on a
    // workspace that never had maps would pass against a hard-coded False
    // or a misspelled binding path. Picking a second folder also proves
    // ExistingMaps.Clear() propagates through the !!Count binding.
    [AvaloniaFact]
    public async Task A_picked_folder_with_no_existing_maps_hides_the_panel()
    {
        var withMap = Directory.CreateTempSubdirectory("djiembed-screen-with").FullName;
        var without = Directory.CreateTempSubdirectory("djiembed-screen-without").FullName;
        try
        {
            File.WriteAllText(Path.Combine(withMap, "DJI_0001.SRT"), "");
            File.WriteAllText(Path.Combine(withMap, "flightmap.html"), "");
            File.WriteAllText(Path.Combine(without, "DJI_0001.SRT"), "");
            var window = ShowWorkspace();
            var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
            var panel = window.GetVisualDescendants().OfType<Border>()
                .Single(b => b.Name == "ExistingMapsPanel");

            await vm.SetFolderAsync(withMap);
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();
            Assert.True(panel.IsEffectivelyVisible);

            await vm.SetFolderAsync(without);
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();
            Assert.False(panel.IsEffectivelyVisible);
        }
        finally
        {
            Directory.Delete(withMap, recursive: true);
            Directory.Delete(without, recursive: true);
        }
    }

    // The item template is most of this panel, and the outer Border's
    // visibility says nothing about it. ExistingMaps is a public collection,
    // so the rows can be driven straight from the VM — no temp dirs needed.
    [AvaloniaFact]
    public void An_existing_map_row_shows_its_title_age_and_live_commands()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.ExistingMaps.Add(new ExistingMap(@"C:\d\flightmap.html", "Flight map",
            DateTime.UtcNow.AddDays(-2), Stale: true));
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var texts = window.GetVisualDescendants().OfType<TextBlock>()
            .Select(t => t.Text ?? "").ToList();
        Assert.Contains("Flight map", texts);
        Assert.Contains("2 days ago", texts);
        Assert.True(window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Name == "StaleNote").IsEffectivelyVisible);
        // Identity, not enabledness, is what proves the
        // $parent[ItemsControl].((vm:WorkspaceViewModel)DataContext) path
        // resolved: an Avalonia Button with a null Command still renders
        // enabled (verified by deleting the binding — every enabled-based
        // assertion still passed), so only the instance is load-bearing.
        var open = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "OpenExistingMapButton");
        Assert.Same(vm.OpenExistingMapCommand, open.Command);
        Assert.Same(vm.ExistingMaps[0], open.CommandParameter);
        Assert.True(open.IsEffectivelyEnabled);   // and CanExecute lets it click
        var reveal = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ShowExistingMapButton");
        Assert.Same(vm.ShowExistingMapInFolderCommand, reveal.Command);
        Assert.Same(vm.ExistingMaps[0], reveal.CommandParameter);
    }

    [AvaloniaFact]
    public void A_fresh_existing_map_hides_the_stale_note()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.ExistingMaps.Add(new ExistingMap(@"C:\d\photomap.html", "Photo map",
            DateTime.UtcNow.AddHours(-3), Stale: false));
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        Assert.False(window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Name == "StaleNote").IsEffectivelyVisible);
    }

    // The preview header's GoHome button says "Process another" only when a
    // run actually produced the map — browsing one the folder already had
    // processed nothing.
    [AvaloniaFact]
    public void Preview_header_labels_the_go_home_button_for_the_step()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.PreviewPath = "flightmap.html";
        vm.PreviewUrl = "http://127.0.0.1:1/flightmap.html";
        vm.Step = FlowStep.Pick;              // an existing map, browsed
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var button = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ClosePreviewButton");
        var label = button.GetVisualDescendants().OfType<TextBlock>().Single();
        Assert.Equal("Close map", label.Text);

        vm.Step = FlowStep.Done;              // a map this run just made
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.Equal("Process another", label.Text);
    }

    // M3c: the Photo map options panel renders only for Photo map, with the
    // Advanced expander closed by default.
    [AvaloniaFact]
    public void Photo_map_mode_shows_its_options_panel_with_advanced_collapsed()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "PhotoOptionsPanel");
        Assert.True(panel.IsEffectivelyVisible);
        var advanced = window.GetVisualDescendants().OfType<Expander>()
            .Single(e => e.Name == "PhotoAdvanced");
        Assert.False(advanced.IsExpanded);
        // The two map panels are mutually exclusive.
        Assert.False(window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "FlightOptionsPanel").IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public void Flight_map_mode_hides_the_photo_options_panel()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "PhotoOptionsPanel");
        Assert.False(panel.IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public void Photo_map_popup_checkboxes_bind_to_the_options_view_model()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var camera = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "PopupCameraCheck");
        Assert.True(camera.IsChecked);
        camera.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.ShowCamera);
        Assert.Contains("--popup-fields", vm.CommandPreview);
    }

    [AvaloniaFact]
    public void Photo_map_clear_output_button_is_bound_to_its_command()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        vm.PhotoOptions.Output = "/out/map.html";
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var clear = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ClearPhotoOutputButton");
        // A Button with a NULL Command still reports IsEffectivelyEnabled ==
        // true, so identity is the only assertion that proves the binding.
        Assert.Same(vm.PhotoOptions.ClearOutputCommand, clear.Command);
    }
}
