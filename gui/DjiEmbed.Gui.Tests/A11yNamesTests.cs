using Avalonia.Automation;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

/// <summary>
/// Accessibility contract (M5b): every interactive control the app
/// declares carries an accessible name. Label-bearing controls may earn
/// theirs from their visible text; value controls (combo/slider/textbox/
/// toggle switch) show a value, not a label, and need an explicit
/// AutomationProperties.Name. Template-internal controls are excluded —
/// they belong to the theme, not to us.
/// </summary>
public class A11yNamesTests
{
    [AvaloniaFact]
    public void Every_interactive_control_carries_an_accessible_name()
    {
        var offenders = new List<string>();
        foreach (var window in RepresentativeWindows())
        {
            window.Show();
            Dispatcher.UIThread.RunJobs();
            foreach (var expander in window.GetVisualDescendants()
                         .OfType<Expander>().ToList())
            {
                expander.IsExpanded = true;
            }
            Dispatcher.UIThread.RunJobs();
            window.UpdateLayout();

            foreach (var control in InteractiveControls(window)
                         .Concat(ExpanderContentControls(window)))
            {
                if (EffectiveLabel(control) is null)
                {
                    offenders.Add(
                        $"{control.GetType().Name} '{control.Name}'");
                }
            }
            window.Close();
        }
        Assert.Empty(offenders.Distinct().OrderBy(o => o));
    }

    private static IEnumerable<Window> RepresentativeWindows()
    {
        static WorkspaceViewModel NewVm() => new(
            null, new DjiEmbedRunner(), new FakeMapServer(null), () => { },
            previewAvailable: static () => false);

        // One window per mode: each mode realizes its own options panel.
        foreach (var mode in WorkspaceMode.All)
        {
            var vm = NewVm();
            if (mode.Kind == WorkspaceModeKind.Convert)
            {
                vm.SetFile(@"C:\demo\DJI_0001.SRT");
            }
            else
            {
                vm.SelectedFolder = @"C:\demo\footage";
            }
            vm.SelectedMode = mode;
            if (mode.Kind == WorkspaceModeKind.Verify)
            {
                // Validate shows the Advanced expander this test opens.
                vm.VerifyOptions.IsValidate = true;
            }
            if (mode.Kind == WorkspaceModeKind.FlightMap)
            {
                // The existing-maps cards realize their per-item buttons.
                vm.ExistingMaps.Add(new ExistingMap(
                    @"C:\demo\footage\flightmap.html", "Flight map",
                    DateTime.UtcNow, Stale: false));
            }
            // Each mode's "Save as" Clear-output button is only IsVisible
            // once Output is set, and only carries a name via its
            // (realized) content — set Output so this mode's window scans
            // it. (Other windows still structurally contain this button,
            // collapsed; the IsEffectivelyVisible filter below skips it
            // there rather than flagging a control nobody can see.)
            switch (mode.Kind)
            {
                case WorkspaceModeKind.FlightMap:
                    vm.FlightOptions.Output = @"C:\demo\custom-map.html";
                    break;
                case WorkspaceModeKind.PhotoMap:
                    vm.PhotoOptions.Output = @"C:\demo\custom-photomap.html";
                    break;
                case WorkspaceModeKind.Embed:
                    vm.EmbedOptions.Output = @"C:\demo\custom-processed";
                    break;
                case WorkspaceModeKind.Convert:
                    vm.ConvertOptions.Output = @"C:\demo\custom.gpx";
                    break;
            }
            yield return Wrap(vm);
        }

        // Done card with an output row (per-item Open button).
        var done = NewVm();
        done.Step = FlowStep.Done;
        done.Outputs.Add(@"C:\demo\footage\flight_map.html");
        yield return Wrap(done);

        // Failed pane with expandable details.
        var failed = NewVm();
        failed.Step = FlowStep.Failed;
        failed.ErrorMessage = "It broke.";
        failed.ErrorDetails = "stack";
        yield return Wrap(failed);

        // Preview toolbar, including its warnings expander.
        var preview = NewVm();
        preview.PreviewPath = "C:/demo/footage/flight_map.html";
        // PreviewUrl (not just PreviewPath) is what ShowPreview actually
        // gates on — without it the whole toolbar stays collapsed.
        preview.PreviewUrl = "file:///C:/demo/footage/flight_map.html";
        preview.Step = FlowStep.Done;
        preview.Warnings.Add("Some clips look duplicated.");
        yield return Wrap(preview);

        // Running step: progress + Cancel.
        var running = NewVm();
        running.Step = FlowStep.Running;
        yield return Wrap(running);

        // Convert → KML with footprints on: realizes the footprint
        // interval slider and camera-model combo, which only show once
        // Footprints is true (and only for geojson/kml formats).
        var convertFootprints = NewVm();
        convertFootprints.SetFile(@"C:\demo\DJI_0001.SRT");
        convertFootprints.SelectedMode = WorkspaceMode.All.First(
            static m => m.Kind == WorkspaceModeKind.Convert);
        convertFootprints.ConvertOptions.SelectedFormat =
            convertFootprints.ConvertOptions.Formats.First(
                static f => f.Key == "kml");
        convertFootprints.ConvertOptions.Footprints = true;
        yield return Wrap(convertFootprints);

        // Convert → CoT: realizes the CoT sampling controls, which only
        // show for the "cot" format.
        var convertCot = NewVm();
        convertCot.SetFile(@"C:\demo\DJI_0001.SRT");
        convertCot.SelectedMode = WorkspaceMode.All.First(
            static m => m.Kind == WorkspaceModeKind.Convert);
        convertCot.ConvertOptions.SelectedFormat =
            convertCot.ConvertOptions.Formats.First(static f => f.Key == "cot");
        yield return Wrap(convertCot);

        // Verify → Sun check: realizes the timezone box, which only shows
        // for that sub-action (the existing per-mode Verify window above
        // exercises Validate, which pins the drift slider instead).
        var verifySun = NewVm();
        verifySun.SelectedFolder = @"C:\demo\footage";
        verifySun.SelectedMode = WorkspaceMode.All.First(
            static m => m.Kind == WorkspaceModeKind.Verify);
        verifySun.VerifyOptions.IsSun = true;
        yield return Wrap(verifySun);

        // The CLI discovery page.
        yield return new Window
        {
            Width = 560, Height = 520,
            Content = new CliDiscoveryView
            { DataContext = new CliDiscoveryViewModel(null, () => { }) },
        };

        static Window Wrap(WorkspaceViewModel vm)
        {
            var view = new WorkspaceView { WebViewGate = static () => false };
            view.DataContext = vm;
            return new Window { Width = 1140, Height = 720, Content = view };
        }
    }

    private static IEnumerable<Control> InteractiveControls(Window window) =>
        window.GetVisualDescendants().OfType<Control>()
            .Where(static c => c is Button or ComboBox or TextBox
                or Slider or ListBox or Expander)
            .Where(static c => c.TemplatedParent is null)
            // A control collapsed by an ancestor (e.g. a Save-as row whose
            // section IsVisible depends on a field this window's VM never
            // sets) never realizes template/content, so it can't earn a
            // label here. It isn't dead code — some other representative
            // window puts it in the state where it IS shown, and that
            // window's pass checks it for real.
            .Where(static c => c.IsEffectivelyVisible);

    // SukiUI's Expander stamps TemplatedParent = the Expander on every
    // control in its authored content, so the main walk's
    // "TemplatedParent is null" filter silently skips everything inside an
    // expanded "Advanced" section (e.g. ConvertTzBox).
    // Widening that filter to admit Expander's TemplatedParent readmits
    // SukiUI's own unnamed template chrome (PART_ borders, header toggle),
    // which lives outside Content — so instead we walk each Expander's
    // Content subtree directly and accept only controls whose
    // TemplatedParent is null (plain authored control) or is the Expander
    // itself (authored control sitting directly in Content); anything
    // deeper with its own TemplatedParent (e.g. a TextBox's internal parts)
    // is template-internal and stays excluded.
    private static IEnumerable<Control> ExpanderContentControls(Window window) =>
        window.GetVisualDescendants().OfType<Expander>()
            .Where(static e => e.Content is Control)
            .SelectMany(static expander =>
            {
                var content = (Control)expander.Content!;
                return new[] { content }.Concat(content.GetVisualDescendants().OfType<Control>())
                    .Where(c => c is Button or ComboBox or TextBox
                        or Slider or ListBox or Expander)
                    .Where(c => c.TemplatedParent is null
                        || ReferenceEquals(c.TemplatedParent, expander))
                    .Where(c => c.IsEffectivelyVisible);
            });

    // Known blind spot: a control added to an IsVisible branch that none of
    // RepresentativeWindows() ever sets True for is never realized, so it
    // is not scanned by either walk above. When adding a new pane/branch,
    // extend RepresentativeWindows() to visit it.

    private static string? EffectiveLabel(Control control)
    {
        var name = AutomationProperties.GetName(control);
        if (!string.IsNullOrWhiteSpace(name))
        {
            return name;
        }
        // Value controls: their content is a value, not a label.
        if (control is ComboBox or TextBox or Slider or ToggleSwitch)
        {
            return null;
        }
        if (control is ContentControl { Content: string s }
            && !string.IsNullOrWhiteSpace(s))
        {
            return s;
        }
        if (control is HeaderedContentControl { Header: string h }
            && !string.IsNullOrWhiteSpace(h))
        {
            return h;
        }
        return control.GetVisualDescendants().OfType<TextBlock>()
            .Select(static t => t.Text)
            .FirstOrDefault(static t => !string.IsNullOrWhiteSpace(t));
    }
}
