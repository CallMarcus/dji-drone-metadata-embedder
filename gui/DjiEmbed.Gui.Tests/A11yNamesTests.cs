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

            foreach (var control in InteractiveControls(window))
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

        // Preview toolbar.
        var preview = NewVm();
        preview.PreviewPath = "C:/demo/footage/flight_map.html";
        preview.Step = FlowStep.Done;
        yield return Wrap(preview);

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
            .Where(static c => c.TemplatedParent is null);

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
