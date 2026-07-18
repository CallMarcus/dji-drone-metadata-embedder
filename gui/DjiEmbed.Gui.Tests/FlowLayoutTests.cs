using Avalonia;
using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;
using Xunit;

namespace DjiEmbed.Gui.Tests;

// The step panels must fill their pane, not dock left at their desired
// width (the v1.21.0 bug behind #292's "content sits awkwardly": buttons
// and the progress bar hugged the left half of the pane). WorkspaceView's
// right pane is one column of a two-column window (GUI 2.0), so the check
// is "centred within its own panel", not "centred in the whole window" —
// the left column's fixed width means the two are no longer the same.
public class FlowLayoutTests
{
    private static Window ShowView(Control view)
    {
        var window = new Window
        {
            Width = 1140,
            Height = 720,
            Content = view,
        };
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        return window;
    }

    private static WorkspaceViewModel WorkspaceVm()
        => new(null, new DjiEmbedRunner(), new MapServer(), () => { });

    private static Button VisibleButton(Window window, string caption) =>
        window.GetVisualDescendants().OfType<Button>()
            .First(b => b.IsEffectivelyVisible
                        && b.GetVisualDescendants().OfType<TextBlock>()
                            .Any(t => t.Text == caption));

    private static void AssertCentredInItsPanel(Visual button)
    {
        var parent = button.GetVisualParent()!;
        var centre = button.Bounds.Left + button.Bounds.Width / 2;
        Assert.InRange(centre, parent.Bounds.Width / 2 - 10, parent.Bounds.Width / 2 + 10);
    }

    [AvaloniaFact]
    public void Done_screen_button_is_centred_in_its_panel()
    {
        var vm = WorkspaceVm();
        vm.Step = FlowStep.Done;
        vm.Outputs.Add(@"C:\demo\processed");
        var window = ShowView(new WorkspaceView { DataContext = vm });

        AssertCentredInItsPanel(VisibleButton(window, "Process another"));
    }

    [AvaloniaFact]
    public void Running_screen_progress_bar_spans_the_content_width()
    {
        var vm = WorkspaceVm();
        vm.Step = FlowStep.Running;
        vm.StatusText = "Embedding your flight data…";
        var window = ShowView(new WorkspaceView { DataContext = vm });

        var bar = window.GetVisualDescendants().OfType<ProgressBar>()
            .First(p => p.IsEffectivelyVisible);
        Assert.True(bar.Bounds.Width >= 400,
            $"progress bar is only {bar.Bounds.Width}px wide");
    }

    [AvaloniaFact]
    public void Failed_screen_button_is_centred_in_its_panel()
    {
        var vm = WorkspaceVm();
        vm.Step = FlowStep.Failed;
        vm.ErrorMessage = "Something went wrong.";
        var window = ShowView(new WorkspaceView { DataContext = vm });

        AssertCentredInItsPanel(VisibleButton(window, "Back"));
    }
}
