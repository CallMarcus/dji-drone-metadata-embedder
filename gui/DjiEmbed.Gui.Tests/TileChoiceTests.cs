using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

// M3c: both map modes offer the same --tile-style keys, so the list lives in
// one place. Order is pinned because it is the ComboBox order (index 0 = the
// CLI default, which every options VM selects at construction).
public class TileChoiceTests
{
    [Fact]
    public void All_lists_the_four_shared_basemaps_in_order()
    {
        Assert.Equal(["osm", "osm-hot", "opentopomap", "cyclosm"],
            TileChoice.All.Select(t => t.Key));
    }

    [Fact]
    public void All_labels_are_human_facing()
    {
        Assert.Equal(["Standard", "Humanitarian", "Topographic", "Cycling"],
            TileChoice.All.Select(t => t.Label));
    }

    [Fact]
    public void Flight_map_options_read_the_shared_list()
    {
        // Assert.Same, not Assert.Equal: a copy-pasted second list would pass
        // an equality check and silently drift from this one later.
        Assert.Same(TileChoice.All, new FlightMapOptionsViewModel().TileStyles);
    }
}
