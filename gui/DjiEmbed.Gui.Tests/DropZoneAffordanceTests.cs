using Avalonia.Controls;
using Avalonia.Controls.Shapes;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;
using Xunit;

namespace DjiEmbed.Gui.Tests;

// #292: the drop zone needs a visible dashed outline and a drag-over
// highlight so it's obvious a folder can be dropped. GUI 2.0's single
// WorkspaceView replaced the per-task pick screens, so the old two-view
// theory (makemap/embed) collapses to one — there's only one drop zone
// to check now, regardless of the selected mode.
public class DropZoneAffordanceTests
{
    private static Window ShowView(Control view)
    {
        var window = new Window { Width = 1140, Height = 720, Content = view };
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        return window;
    }

    private static WorkspaceView PickView() => new()
    {
        DataContext = new WorkspaceViewModel(
            null, new DjiEmbedRunner(), new MapServer(), () => { }),
    };

    [AvaloniaFact]
    public void Pick_screen_drop_zone_has_a_dashed_outline()
    {
        var window = ShowView(PickView());
        var outlines = window.GetVisualDescendants().OfType<Rectangle>()
            .Where(r => r.StrokeDashArray is { Count: > 0 });
        Assert.NotEmpty(outlines);
    }

    [AvaloniaFact]
    public void Pick_screen_names_its_drop_zone()
    {
        var window = ShowView(PickView());
        var zone = window.GetVisualDescendants().OfType<Border>()
            .FirstOrDefault(b => b.Name == "DropZone");
        Assert.NotNull(zone);
    }

    [AvaloniaFact]
    public void Drag_over_toggles_the_dragover_class_on_the_zone()
    {
        var zone = new Border();
        FolderPicking.SetDragOver(zone, true);
        Assert.Contains("dragover", zone.Classes);
        FolderPicking.SetDragOver(zone, false);
        Assert.DoesNotContain("dragover", zone.Classes);
    }
}
