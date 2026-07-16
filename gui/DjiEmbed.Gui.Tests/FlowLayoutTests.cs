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

// The step panels must fill the window, not dock left at their desired
// width (the v1.21.0 bug behind #292's "content sits awkwardly": buttons
// and the progress bar hugged the left half of the window).
public class FlowLayoutTests
{
    private const double WindowWidth = 560;

    private static Window ShowView(Control view)
    {
        var window = new Window
        {
            Width = WindowWidth,
            Height = 520,
            Content = view,
        };
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        return window;
    }

    private static EmbedTelemetryViewModel EmbedVm()
        => new(null, new DjiEmbedRunner(), () => { });

    private static double CentreXInWindow(Visual control, Window window) =>
        control.TranslatePoint(
            new Point(control.Bounds.Width / 2, 0), window)!.Value.X;

    private static Button VisibleButton(Window window, string caption) =>
        window.GetVisualDescendants().OfType<Button>()
            .First(b => b.IsEffectivelyVisible
                        && b.GetVisualDescendants().OfType<TextBlock>()
                            .Any(t => t.Text == caption));

    [AvaloniaFact]
    public void Done_screen_button_is_centred_in_the_window()
    {
        var vm = EmbedVm();
        vm.Step = FlowStep.Done;
        vm.Outputs.Add(@"C:\demo\processed");
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });

        var centre = CentreXInWindow(VisibleButton(window, "Done"), window);
        Assert.InRange(centre, WindowWidth / 2 - 10, WindowWidth / 2 + 10);
    }

    [AvaloniaFact]
    public void Running_screen_progress_bar_spans_the_content_width()
    {
        var vm = EmbedVm();
        vm.Step = FlowStep.Running;
        vm.StatusText = "Embedding your flight data…";
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });

        var bar = window.GetVisualDescendants().OfType<ProgressBar>()
            .First(p => p.IsEffectivelyVisible);
        Assert.True(bar.Bounds.Width >= 400,
            $"progress bar is only {bar.Bounds.Width}px wide");
    }

    [AvaloniaFact]
    public void Failed_screen_button_is_centred_in_the_window()
    {
        var vm = EmbedVm();
        vm.Step = FlowStep.Failed;
        vm.ErrorMessage = "Something went wrong.";
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });

        var centre = CentreXInWindow(VisibleButton(window, "Back"), window);
        Assert.InRange(centre, WindowWidth / 2 - 10, WindowWidth / 2 + 10);
    }
}
