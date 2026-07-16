using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.Input.Platform;
using Avalonia.Threading;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;
using Xunit;

namespace DjiEmbed.Gui.Tests;

// #292: the failure screen should show the tail of the captured stderr
// (not a wall of text) and offer "Copy details" so bug reports arrive
// with the full error output.
public class FailureDetailsTests
{
    private static EmbedTelemetryViewModel FailedVm(string details)
    {
        var vm = new EmbedTelemetryViewModel(
            null, new DjiEmbedRunner(), () => { });
        vm.Step = FlowStep.Failed;
        vm.ErrorMessage = "Something went wrong.";
        vm.ErrorDetails = details;
        return vm;
    }

    private static Window ShowView(Control view)
    {
        var window = new Window { Width = 560, Height = 520, Content = view };
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        // The details live inside the collapsed expander; open it the way
        // a user would before looking at them.
        foreach (var expander in
                 window.GetVisualDescendants().OfType<Expander>().ToList())
        {
            expander.IsExpanded = true;
        }
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        return window;
    }

    [Fact]
    public void Short_details_are_shown_whole()
    {
        var vm = FailedVm("line one\nline two");
        Assert.Equal("line one\nline two", vm.ErrorDetailsTail);
    }

    [Fact]
    public void Long_details_are_cut_to_the_last_lines()
    {
        var lines = Enumerable.Range(1, 40).Select(i => $"line {i}");
        var vm = FailedVm(string.Join('\n', lines));
        var tail = vm.ErrorDetailsTail!;
        Assert.Contains("line 40", tail);
        Assert.DoesNotContain("line 1\n", tail);
        // The cut is announced, so nobody thinks this is everything.
        Assert.Contains("omitted", tail);
    }

    [Fact]
    public void No_details_means_no_tail()
    {
        var vm = new EmbedTelemetryViewModel(
            null, new DjiEmbedRunner(), () => { });
        Assert.Null(vm.ErrorDetailsTail);
    }

    [AvaloniaFact]
    public void Failed_screen_shows_the_tail_not_the_full_dump()
    {
        var lines = Enumerable.Range(1, 40).Select(i => $"line {i}");
        var vm = FailedVm(string.Join('\n', lines));
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });
        var texts = window.GetVisualDescendants().OfType<TextBlock>()
            .Select(t => t.Text ?? "").ToList();
        Assert.Contains(texts, t => t.Contains("line 40"));
        Assert.DoesNotContain(texts, t => t.Contains("line 1\n"));
    }

    [AvaloniaFact]
    public async Task Copy_details_puts_the_full_output_on_the_clipboard()
    {
        var lines = Enumerable.Range(1, 40).Select(i => $"line {i}");
        var vm = FailedVm(string.Join('\n', lines));
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });

        var copy = window.GetVisualDescendants().OfType<Button>()
            .First(b => b.GetVisualDescendants().OfType<TextBlock>()
                .Any(t => t.Text == "Copy details"));
        copy.Command?.Execute(copy.CommandParameter);
        if (copy.Command is null)
        {
            copy.RaiseEvent(new Avalonia.Interactivity.RoutedEventArgs(
                Button.ClickEvent));
        }
        Dispatcher.UIThread.RunJobs();

        var copied = await window.Clipboard!.TryGetTextAsync();
        Assert.Contains("line 1", copied);
        Assert.Contains("line 40", copied);
    }
}
