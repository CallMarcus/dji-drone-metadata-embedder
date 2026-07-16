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
// highlight so it's obvious a folder can be dropped.
public class DropZoneAffordanceTests
{
    private static Window ShowView(Control view)
    {
        var window = new Window { Width = 560, Height = 520, Content = view };
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        return window;
    }

    public static TheoryData<string> PickViews() => new() { "makemap", "embed" };

    private static Control PickView(string kind) => kind switch
    {
        "makemap" => new MakeMapView
        {
            DataContext = new MakeMapViewModel(
                null, new DjiEmbedRunner(), () => { }),
        },
        _ => new EmbedTelemetryView
        {
            DataContext = new EmbedTelemetryViewModel(
                null, new DjiEmbedRunner(), () => { }),
        },
    };

    [AvaloniaTheory]
    [MemberData(nameof(PickViews))]
    public void Pick_screen_drop_zone_has_a_dashed_outline(string kind)
    {
        var window = ShowView(PickView(kind));
        var outlines = window.GetVisualDescendants().OfType<Rectangle>()
            .Where(r => r.StrokeDashArray is { Count: > 0 });
        Assert.NotEmpty(outlines);
    }

    [AvaloniaTheory]
    [MemberData(nameof(PickViews))]
    public void Pick_screen_names_its_drop_zone(string kind)
    {
        var window = ShowView(PickView(kind));
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
