using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.Input.Platform;
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
    public void Mode_strip_shows_exactly_the_six_modes()
    {
        var window = ShowWorkspace();
        var strip = window.GetVisualDescendants().OfType<ListBox>()
            .Single(l => l.Name == "ModeStrip");
        Assert.Equal(6, strip.ItemCount);
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

    // Manual plan §2.6 "Copy is exact": the strip's Copy button must put the
    // preview on the clipboard byte-identically — a transformation on the way
    // out would break the paste-into-a-terminal promise.
    [AvaloniaFact]
    public async Task Copy_command_puts_the_exact_preview_on_the_clipboard()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;

        window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "CopyCommandButton")
            .RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(
                Button.ClickEvent));
        Dispatcher.UIThread.RunJobs();

        var copied = await window.Clipboard!.TryGetTextAsync();
        Assert.Equal(vm.CommandPreview, copied);
        Assert.Equal("dji-embed flightmap <folder> -r", copied);
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

    // #336: the Flight panel had zero interactive-control binding tests.
    // Compiled bindings catch a mistyped property PATH at build time; the
    // surviving failure modes are a control bound to the wrong OBJECT
    // (PhotoOptions.Recursive here compiles fine) or a dropped binding
    // attribute — so flip every control from the CONTROL side and assert its
    // own options VM moved, and the strip with it.
    [AvaloniaFact]
    public void Flight_map_controls_bind_to_the_flight_options_view_model()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;

        var recursive = window.GetVisualDescendants().OfType<ToggleSwitch>()
            .Single(t => t.Name == "FlightRecursiveToggle");
        Assert.True(recursive.IsChecked);
        recursive.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.FlightOptions.Recursive);
        Assert.DoesNotContain(" -r", vm.CommandPreview);

        var style = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "FlightStyleCombo");
        Assert.Same(vm.FlightOptions.TileStyles, style.ItemsSource);
        style.SelectedItem =
            vm.FlightOptions.TileStyles.Single(t => t.Key == "opentopomap");
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("opentopomap", vm.FlightOptions.SelectedTileStyle.Key);
        Assert.Contains("--tile-style opentopomap", vm.CommandPreview);

        var privacy = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "FlightPrivacyCombo");
        Assert.Same(vm.FlightOptions.PrivacyOptions, privacy.ItemsSource);
        privacy.SelectedItem = vm.FlightOptions.PrivacyOptions
            .Single(p => p.Value == MapPrivacy.Fuzz);
        Dispatcher.UIThread.RunJobs();
        Assert.Equal(MapPrivacy.Fuzz, vm.FlightOptions.SelectedPrivacy.Value);
        Assert.Contains("--redact fuzz", vm.CommandPreview);

        var joinGap = window.GetVisualDescendants().OfType<Slider>()
            .Single(s => s.Name == "JoinGapSlider");
        joinGap.Value = 0;
        Dispatcher.UIThread.RunJobs();
        Assert.Equal(0, vm.FlightOptions.JoinGap);
        Assert.Contains("--join-gap 0", vm.CommandPreview);

        var exportAll = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "FlightExportAllCheck");
        exportAll.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.FlightOptions.ExportAll);
        Assert.Contains("--format all", vm.CommandPreview);

        var tz = window.GetVisualDescendants().OfType<TextBox>()
            .Single(t => t.Name == "FlightTzBox");
        tz.Text = "+02:00";
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("+02:00", vm.FlightOptions.TzOffset);
        Assert.Contains("--tz-offset +02:00", vm.CommandPreview);

        var title = window.GetVisualDescendants().OfType<TextBox>()
            .Single(t => t.Name == "FlightTitleBox");
        title.Text = "Alps";
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("Alps", vm.FlightOptions.Title);
        Assert.Contains("--title Alps", vm.CommandPreview);
    }

    [AvaloniaFact]
    public void Flight_map_clear_output_button_is_bound_to_its_command()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.FlightOptions.Output = "/out/map.html";
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var clear = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ClearOutputButton");
        // A Button with a NULL Command still reports IsEffectivelyEnabled ==
        // true, so identity is the only assertion that proves the binding.
        Assert.Same(vm.FlightOptions.ClearOutputCommand, clear.Command);
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

    // #336, Photo panel: the controls the camera-checkbox test above does not
    // reach — including the four popup checkboxes that were named but never
    // driven. Cumulative unchecks walk --popup-fields down to one name, so
    // every flip shows up in the strip, not just in the VM.
    [AvaloniaFact]
    public void Photo_map_controls_bind_to_the_photo_options_view_model()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var recursive = window.GetVisualDescendants().OfType<ToggleSwitch>()
            .Single(t => t.Name == "PhotoRecursiveToggle");
        Assert.True(recursive.IsChecked);
        recursive.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.Recursive);
        Assert.DoesNotContain(" -r", vm.CommandPreview);

        var style = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "PhotoStyleCombo");
        Assert.Same(vm.PhotoOptions.TileStyles, style.ItemsSource);
        style.SelectedItem =
            vm.PhotoOptions.TileStyles.Single(t => t.Key == "cyclosm");
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("cyclosm", vm.PhotoOptions.SelectedTileStyle.Key);
        Assert.Contains("--tile-style cyclosm", vm.CommandPreview);

        var privacy = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "PhotoPrivacyCombo");
        Assert.Same(vm.PhotoOptions.PrivacyOptions, privacy.ItemsSource);
        privacy.SelectedItem = vm.PhotoOptions.PrivacyOptions
            .Single(p => p.Value == MapPrivacy.Fuzz);
        Dispatcher.UIThread.RunJobs();
        Assert.Equal(MapPrivacy.Fuzz, vm.PhotoOptions.SelectedPrivacy.Value);
        Assert.Contains("--redact fuzz", vm.CommandPreview);

        var checkboxes = window.GetVisualDescendants().OfType<CheckBox>().ToList();
        var name = checkboxes.Single(c => c.Name == "PopupNameCheck");
        name.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.ShowName);
        Assert.Contains("--popup-fields timestamp,camera,altitude,credit",
            vm.CommandPreview);

        var time = checkboxes.Single(c => c.Name == "PopupTimeCheck");
        time.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.ShowTimestamp);
        Assert.Contains("--popup-fields camera,altitude,credit", vm.CommandPreview);

        var altitude = checkboxes.Single(c => c.Name == "PopupAltitudeCheck");
        altitude.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.ShowAltitude);
        Assert.Contains("--popup-fields camera,credit", vm.CommandPreview);

        var credit = checkboxes.Single(c => c.Name == "PopupCreditCheck");
        credit.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.ShowCredit);
        Assert.Contains("--popup-fields camera", vm.CommandPreview);

        var exportAll = checkboxes.Single(c => c.Name == "PhotoExportAllCheck");
        exportAll.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.PhotoOptions.ExportAll);
        Assert.Contains("--format all", vm.CommandPreview);

        var title = window.GetVisualDescendants().OfType<TextBox>()
            .Single(t => t.Name == "PhotoTitleBox");
        title.Text = "Beach";
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("Beach", vm.PhotoOptions.Title);
        Assert.Contains("--title Beach", vm.CommandPreview);
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

    // Branch review: photomap links pins to the originals with an href
    // RELATIVE to the HTML file, so redirecting "Save map to" outside the
    // source folder silently breaks every "open the original" link.
    [AvaloniaFact]
    public async Task Link_reach_note_appears_only_when_the_output_would_leave_the_source_folder()
    {
        var dir = Directory.CreateTempSubdirectory("djiembed-screen-linkreach").FullName;
        var elsewhere = Directory.CreateTempSubdirectory("djiembed-screen-linkreach-out").FullName;
        try
        {
            File.WriteAllText(Path.Combine(dir, "IMG_1.JPG"), "");
            var window = ShowWorkspace();
            var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
            await vm.SetFolderAsync(dir);
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();

            var note = window.GetVisualDescendants().OfType<TextBlock>()
                .Single(t => t.Name == "LinkReachNote");
            Assert.False(note.IsEffectivelyVisible);

            vm.PhotoOptions.Output = Path.Combine(elsewhere, "photomap.html");
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();
            Assert.True(note.IsEffectivelyVisible);
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
            Directory.Delete(elsewhere, recursive: true);
        }
    }

    // The one privacy-relevant message in the panel: a fuzzed map still
    // leaks exact GPS through linked originals. Proves the IsVisible
    // binding path itself, not just the ViewModel property it reads.
    [AvaloniaFact]
    public void Fuzz_caveat_note_tracks_privacy_and_link_originals()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var note = window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Name == "FuzzCaveatNote");
        Assert.False(note.IsEffectivelyVisible);   // defaults: Keep + linked

        vm.PhotoOptions.SelectedPrivacy = vm.PhotoOptions.PrivacyOptions[1];   // Fuzz
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.True(note.IsEffectivelyVisible);

        vm.PhotoOptions.LinkOriginals = false;
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.False(note.IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public void Photo_map_link_originals_checkbox_binds_to_the_options_view_model()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var link = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "LinkOriginalsCheck");
        Assert.True(link.IsChecked);
        link.IsChecked = false;
        Dispatcher.UIThread.RunJobs();
        Assert.False(vm.PhotoOptions.LinkOriginals);
        Assert.DoesNotContain("--link-originals", vm.CommandPreview);
    }

    [AvaloniaFact]
    public void Embed_mode_shows_its_options_panel_with_advanced_collapsed()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "EmbedOptionsPanel");
        Assert.True(panel.IsEffectivelyVisible);
        var advanced = window.GetVisualDescendants().OfType<Expander>()
            .Single(e => e.Name == "EmbedAdvanced");
        Assert.False(advanced.IsExpanded);
        // All three options panels are mutually exclusive.
        Assert.False(window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "FlightOptionsPanel").IsEffectivelyVisible);
        Assert.False(window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "PhotoOptionsPanel").IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public void Flight_map_mode_hides_the_embed_options_panel()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "EmbedOptionsPanel");
        Assert.False(panel.IsEffectivelyVisible);
    }

    [AvaloniaFact]
    public void Embed_checkboxes_bind_to_their_own_options_view_model()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var home = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "ExtractHomeCheck");
        Assert.False(home.IsChecked);
        home.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.EmbedOptions.ExtractHome);
        Assert.Contains("--extract-home", vm.CommandPreview);

        // A wrong-OBJECT binding (e.g. PhotoOptions.X in this panel) compiles
        // fine, so assert the flag actually lands in the Embed argv.
        var dat = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "DatAutoCheck");
        dat.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.EmbedOptions.DatAuto);
        Assert.Contains("--dat-auto", vm.CommandPreview);
    }

    // #336, Embed panel: the two Advanced checkboxes that were named but
    // never driven by the sibling test above.
    [AvaloniaFact]
    public void Embed_advanced_checkboxes_bind_to_the_embed_options_view_model()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var exiftool = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "ExifToolCheck");
        Assert.False(exiftool.IsChecked);
        exiftool.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.EmbedOptions.UseExifTool);
        Assert.Contains("--exiftool", vm.CommandPreview);

        var audio = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "AudioSidecarCheck");
        Assert.False(audio.IsChecked);
        audio.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.EmbedOptions.AudioSidecar);
        Assert.Contains("--audio-sidecar", vm.CommandPreview);
    }

    [AvaloniaFact]
    public void Embed_clear_output_button_is_bound_to_its_command()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        vm.EmbedOptions.Output = "/out/copies";
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var clear = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ClearEmbedOutputButton");
        // A Button with a NULL Command still reports IsEffectivelyEnabled ==
        // true, so identity is the only assertion that proves the binding.
        Assert.Same(vm.EmbedOptions.ClearOutputCommand, clear.Command);
    }

    // #335: the three Choose… click handlers differ only in which panel's
    // Output they assign — a cross-wired copy-paste (Photo's button on the
    // flight handler, say) keeps every other test green while the click
    // lands in the wrong panel. The picker seams are pinned so no native
    // dialog ever opens headless; the OTHER two outputs are asserted
    // untouched because that is precisely the failure shape.
    [AvaloniaFact]
    public void Flight_choose_button_routes_the_picked_path_to_the_flight_output()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var view = (WorkspaceView)window.Content!;
        var vm = (WorkspaceViewModel)view.DataContext!;
        var titles = new List<string>();
        view.SavePicker = (_, title, _) =>
        {
            titles.Add(title);
            return Task.FromResult<string?>("/picked/flightmap.html");
        };

        window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ChooseOutputButton")
            .RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(Button.ClickEvent));
        Dispatcher.UIThread.RunJobs();

        Assert.Equal(["Save the flight map as"], titles);
        Assert.Equal("/picked/flightmap.html", vm.FlightOptions.Output);
        Assert.Equal("", vm.PhotoOptions.Output);
        Assert.Equal("", vm.EmbedOptions.Output);
    }

    [AvaloniaFact]
    public void Photo_choose_button_routes_the_picked_path_to_the_photo_output()
    {
        var window = ShowWorkspace();
        var view = (WorkspaceView)window.Content!;
        var vm = (WorkspaceViewModel)view.DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        var titles = new List<string>();
        view.SavePicker = (_, title, _) =>
        {
            titles.Add(title);
            return Task.FromResult<string?>("/picked/photomap.html");
        };

        window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ChoosePhotoOutputButton")
            .RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(Button.ClickEvent));
        Dispatcher.UIThread.RunJobs();

        Assert.Equal(["Save the photo map as"], titles);
        Assert.Equal("/picked/photomap.html", vm.PhotoOptions.Output);
        Assert.Equal("", vm.FlightOptions.Output);
        Assert.Equal("", vm.EmbedOptions.Output);
    }

    [AvaloniaFact]
    public void Embed_choose_button_routes_the_picked_folder_to_the_embed_output()
    {
        var window = ShowWorkspace();
        var view = (WorkspaceView)window.Content!;
        var vm = (WorkspaceViewModel)view.DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        // Embed's -o is a DIRECTORY, so this button must take the folder
        // picker, never the save dialog — the decoy would betray it.
        view.SavePicker = static (_, _, _) =>
            Task.FromResult<string?>("/decoy/from-the-save-dialog.html");
        view.OutputFolderPicker = static (_, _) =>
            Task.FromResult<string?>("/picked/copies");

        window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ChooseEmbedOutputButton")
            .RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(Button.ClickEvent));
        Dispatcher.UIThread.RunJobs();

        Assert.Equal("/picked/copies", vm.EmbedOptions.Output);
        Assert.Equal("", vm.FlightOptions.Output);
        Assert.Equal("", vm.PhotoOptions.Output);
    }

    // The one privacy-relevant message in this panel: "Remove GPS entirely"
    // empties the launch point the checkbox just asked for. Proves the
    // IsVisible binding path, not just the ViewModel property behind it.
    [AvaloniaFact]
    public void Home_emptied_note_appears_only_when_dropping_and_extracting()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var note = window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Name == "HomeEmptiedNote");
        Assert.False(note.IsEffectivelyVisible);   // defaults: Keep, no home

        vm.EmbedOptions.ExtractHome = true;
        vm.EmbedOptions.SelectedPrivacy = vm.EmbedOptions.PrivacyOptions
            .Single(p => p.Value == TelemetryPrivacy.Drop);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.True(note.IsEffectivelyVisible);

        vm.EmbedOptions.ExtractHome = false;
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.False(note.IsEffectivelyVisible);
    }

    // The Advanced expander's counterpart to the home note: ExifTool can't
    // write MKV, and the curated container combo sits three rows above, so
    // the no-op pair is two clicks away. Proves the IsVisible binding path.
    [AvaloniaFact]
    public void Exiftool_mkv_note_appears_only_when_exiftool_meets_mkv()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var note = window.GetVisualDescendants().OfType<TextBlock>()
            .Single(t => t.Name == "ExifToolMkvNote");
        Assert.False(note.IsEffectivelyVisible);   // defaults: MP4, no ExifTool

        vm.EmbedOptions.UseExifTool = true;
        vm.EmbedOptions.SelectedContainer =
            vm.EmbedOptions.Containers.Single(c => c.Key == "mkv");
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.True(note.IsEffectivelyVisible);

        vm.EmbedOptions.UseExifTool = false;
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.False(note.IsEffectivelyVisible);
    }

    // Driven from the CONTROL side on purpose: the note test above mutates
    // SelectedPrivacy on the ViewModel and so never exercises the combo's
    // binding. A wrong-object ItemsSource compiles, renders a plausible
    // list, and silently cannot round-trip a selection.
    [AvaloniaFact]
    public void Embed_combo_boxes_round_trip_a_selection_into_the_argv()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var privacy = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "EmbedPrivacyCombo");
        Assert.Same(vm.EmbedOptions.PrivacyOptions, privacy.ItemsSource);
        privacy.SelectedItem = vm.EmbedOptions.PrivacyOptions
            .Single(p => p.Value == TelemetryPrivacy.Drop);

        var container = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "ContainerCombo");
        Assert.Same(vm.EmbedOptions.Containers, container.ItemsSource);
        container.SelectedItem =
            vm.EmbedOptions.Containers.Single(c => c.Key == "mkv");

        Dispatcher.UIThread.RunJobs();
        Assert.Contains("--redact drop", vm.CommandPreview);
        Assert.Contains("--container mkv", vm.CommandPreview);
    }

    // #340: the CLI strip's promise — what is shown is what runs — only
    // holds if nothing that feeds it can change during a run. SOURCE, MODE
    // and the options panels freeze; the strip's Copy button does not
    // (what it copies IS what is running).
    [AvaloniaFact]
    public async Task Left_column_freezes_while_a_run_is_in_flight()
    {
        var dir = Directory.CreateTempSubdirectory("djiembed-screen-busy").FullName;
        try
        {
            var cli = FakeCli.WriteEventStream(dir,
            [
                """{"v": 1, "event": "start", "command": "flightmap", "total": 1}""",
                """{"v": 1, "event": "result", "ok": true, "outputs": ["flightmap.html"], "summary": {}}""",
            ]);
            var gate = new TaskCompletionSource();
            Func<string, FolderContents> inspect = _ => new FolderContents(
                true, false, false, true, false, false, null, null);
            var vm = new WorkspaceViewModel(cli, new DjiEmbedRunner(),
                new FakeMapServer(null), () => { },
                previewAvailable: static () => false,
                folderInspector: d => inspect(d));
            var window = ShowWorkspace(vm);
            await vm.SetFolderAsync(dir);
            inspect = _ =>
            {
                gate.Task.Wait();
                return new FolderContents(
                    true, false, false, true, false, false, null, null);
            };

            var run = vm.RunCommand.ExecuteAsync(null);
            Dispatcher.UIThread.RunJobs();

            var byName = (string name) => window.GetVisualDescendants()
                .OfType<Control>().Single(c => c.Name == name);
            Assert.False(byName("SourceCard").IsEnabled);
            Assert.False(byName("ModeCard").IsEnabled);
            Assert.False(byName("FlightOptionsPanel").IsEnabled);
            Assert.False(byName("PhotoOptionsPanel").IsEnabled);
            Assert.False(byName("EmbedOptionsPanel").IsEnabled);
            Assert.False(byName("ConvertOptionsPanel").IsEnabled);
            Assert.True(byName("CopyCommandButton").IsEffectivelyEnabled);

            gate.SetResult();
            await run;
            Dispatcher.UIThread.RunJobs();
            Assert.True(byName("SourceCard").IsEnabled);
            Assert.True(byName("ModeCard").IsEnabled);
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    // M4a: the SOURCE card's second button ("Choose a file…") routes
    // through the same test-seam mould as SavePicker/OutputFolderPicker —
    // pinned here so the picked path lands on SelectedFile without ever
    // touching a real file dialog headless.
    [AvaloniaFact]
    public void Choose_file_button_routes_through_the_file_picker_seam()
    {
        var view = new WorkspaceView { WebViewGate = static () => false };
        var vm = NewWorkspaceViewModel();
        view.FilePicker = static (_) => Task.FromResult<string?>("C:/x/DJI_1.SRT");
        view.DataContext = vm;
        var button = view.FindControl<Button>("ChooseFileButton")!;
        button.RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(Button.ClickEvent));
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("C:/x/DJI_1.SRT", vm.SelectedFile);
    }

    // M4a: the Convert options panel renders only for Convert, with the
    // Advanced expander closed by default. The panel's freeze-while-busy
    // behaviour is covered alongside the other three panels' by
    // Left_column_freezes_while_a_run_is_in_flight (#340).
    [AvaloniaFact]
    public void Convert_mode_shows_the_options_panel_with_advanced_collapsed()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "ConvertOptionsPanel");
        Assert.True(panel.IsEffectivelyVisible);
        var advanced = window.GetVisualDescendants().OfType<Expander>()
            .Single(e => e.Name == "ConvertAdvanced");
        Assert.False(advanced.IsExpanded);
    }

    [AvaloniaFact]
    public void Non_convert_mode_hides_the_convert_options_panel()
    {
        var window = ShowWorkspace();   // default mode Flight map
        var panel = window.GetVisualDescendants().OfType<Border>()
            .Single(b => b.Name == "ConvertOptionsPanel");
        Assert.False(panel.IsEffectivelyVisible);
    }

    // #336-style: flip every control from the CONTROL side and assert its
    // own options VM moved, catching a wrong-OBJECT binding that a
    // compiled-binding build would let through.
    [AvaloniaFact]
    public void Convert_panel_controls_bind_the_convert_options()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var format = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "ConvertFormatCombo");
        Assert.Same(vm.ConvertOptions.Formats, format.ItemsSource);
        format.SelectedItem = vm.ConvertOptions.Formats.Single(f => f.Key == "kml");
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("kml", vm.ConvertOptions.SelectedFormat.Key);
        Assert.Contains("convert kml", vm.CommandPreview);

        var privacy = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "ConvertPrivacyCombo");
        Assert.Same(vm.ConvertOptions.PrivacyOptions, privacy.ItemsSource);
        privacy.SelectedItem = vm.ConvertOptions.PrivacyOptions
            .Single(p => p.Value == TelemetryPrivacy.Fuzz);
        Dispatcher.UIThread.RunJobs();
        Assert.Equal(TelemetryPrivacy.Fuzz, vm.ConvertOptions.SelectedPrivacy.Value);
        Assert.Contains("--redact fuzz", vm.CommandPreview);

        var tz = window.GetVisualDescendants().OfType<TextBox>()
            .Single(t => t.Name == "ConvertTzBox");
        tz.Text = "+02:00";
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("+02:00", vm.ConvertOptions.TzOffset);
        Assert.Contains("--tz-offset +02:00", vm.CommandPreview);

        var footprints = window.GetVisualDescendants().OfType<CheckBox>()
            .Single(c => c.Name == "FootprintsCheck");
        Assert.False(footprints.IsChecked);
        footprints.IsChecked = true;
        Dispatcher.UIThread.RunJobs();
        Assert.True(vm.ConvertOptions.Footprints);
        Assert.Contains("--footprint", vm.CommandPreview);

        var interval = window.GetVisualDescendants().OfType<Slider>()
            .Single(s => s.Name == "FootprintIntervalSlider");
        interval.Value = 5;
        Dispatcher.UIThread.RunJobs();
        Assert.Equal(5, vm.ConvertOptions.FootprintInterval);
        Assert.Contains("--footprint-interval 5", vm.CommandPreview);

        var model = window.GetVisualDescendants().OfType<ComboBox>()
            .Single(c => c.Name == "ConvertModelCombo");
        Assert.Same(vm.ConvertOptions.Models, model.ItemsSource);
        model.SelectedItem = vm.ConvertOptions.Models.Single(m => m.Key == "air3");
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("air3", vm.ConvertOptions.SelectedModel.Key);
        Assert.Contains("--model air3", vm.CommandPreview);

        // Switch to cot to reach the CoT-only controls.
        format.SelectedItem = vm.ConvertOptions.Formats.Single(f => f.Key == "cot");
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var cotInterval = window.GetVisualDescendants().OfType<Slider>()
            .Single(s => s.Name == "CotIntervalSlider");
        cotInterval.Value = 3;
        Dispatcher.UIThread.RunJobs();
        Assert.Equal(3, vm.ConvertOptions.CotInterval);
        Assert.Contains("--interval 3", vm.CommandPreview);

        var cotType = window.GetVisualDescendants().OfType<TextBox>()
            .Single(t => t.Name == "CotTypeBox");
        cotType.Text = "a-h-A";
        Dispatcher.UIThread.RunJobs();
        Assert.Equal("a-h-A", vm.ConvertOptions.CotType);
        Assert.Contains("--cot-type a-h-A", vm.CommandPreview);

        var clear = window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ClearConvertOutputButton");
        // A Button with a NULL Command still reports IsEffectivelyEnabled ==
        // true, so identity is the only assertion that proves the binding.
        Assert.Same(vm.ConvertOptions.ClearOutputCommand, clear.Command);
    }

    [AvaloniaFact]
    public async Task Convert_conditional_sections_follow_the_format()
    {
        var window = ShowWorkspace();
        var vm = (WorkspaceViewModel)((WorkspaceView)window.Content!).DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        var footprintSection = window.GetVisualDescendants().OfType<StackPanel>()
            .Single(s => s.Name == "FootprintSection");
        var cotSection = window.GetVisualDescendants().OfType<StackPanel>()
            .Single(s => s.Name == "CotSection");
        var saveSection = window.GetVisualDescendants().OfType<StackPanel>()
            .Single(s => s.Name == "ConvertSaveSection");

        // Default format is gpx: neither conditional section, no file source.
        Assert.False(footprintSection.IsEffectivelyVisible);
        Assert.False(cotSection.IsEffectivelyVisible);
        Assert.False(saveSection.IsEffectivelyVisible);

        vm.ConvertOptions.SelectedFormat =
            vm.ConvertOptions.Formats.Single(f => f.Key == "kml");
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.True(footprintSection.IsEffectivelyVisible);
        Assert.False(cotSection.IsEffectivelyVisible);

        vm.ConvertOptions.SelectedFormat =
            vm.ConvertOptions.Formats.Single(f => f.Key == "cot");
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.False(footprintSection.IsEffectivelyVisible);
        Assert.True(cotSection.IsEffectivelyVisible);

        vm.SetFile("C:/clips/DJI_0001.SRT");
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        Assert.True(saveSection.IsEffectivelyVisible);

        var dir = Directory.CreateTempSubdirectory("djiembed-screen-convert-savesection").FullName;
        try
        {
            await vm.SetFolderAsync(dir);
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();
            Assert.False(saveSection.IsEffectivelyVisible);   // a folder source has no save-as
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    // #335-style: the seam is pinned so no native dialog opens headless, and
    // the suggested name proves the picker is wired with the SOURCE file's
    // stem and the currently-selected format's own suffix.
    [AvaloniaFact]
    public void Choose_convert_output_routes_through_the_typed_save_picker()
    {
        var window = ShowWorkspace();
        var view = (WorkspaceView)window.Content!;
        var vm = (WorkspaceViewModel)view.DataContext!;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        vm.SetFile("C:/clips/DJI_0001.SRT");
        vm.ConvertOptions.SelectedFormat =
            vm.ConvertOptions.Formats.Single(f => f.Key == "kml");
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();

        string? suggestedName = null;
        string? pattern = null;
        view.ConvertSavePicker = (_, _, name, _, ext) =>
        {
            suggestedName = name;
            pattern = ext;
            return Task.FromResult<string?>("C:/x/DJI_0001.kml");
        };

        window.GetVisualDescendants().OfType<Button>()
            .Single(b => b.Name == "ChooseConvertOutputButton")
            .RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(Button.ClickEvent));
        Dispatcher.UIThread.RunJobs();

        Assert.Equal("DJI_0001.kml", suggestedName);
        Assert.Equal("*.kml", pattern);
        Assert.Equal("C:/x/DJI_0001.kml", vm.ConvertOptions.Output);
    }
}
