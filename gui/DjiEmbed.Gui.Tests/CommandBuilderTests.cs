using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

// M3a: one source of truth for each mode's argv (no --progress; the runner
// appends that). These goldens pin today's behaviour so later option slices
// can only extend it deliberately.
public class CommandBuilderTests
{
    [Fact]
    public void Flight_map_builds_recursive_flightmap()
    {
        string[] expected = ["flightmap", "/x", "-r"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.FlightMap, "/x"));
    }

    [Fact]
    public void Photo_map_links_originals_for_the_pano_viewer()
    {
        string[] expected = ["photomap", "/x", "-r", "--link-originals"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.PhotoMap, "/x"));
    }

    [Fact]
    public void Embed_is_bare()
    {
        string[] expected = ["embed", "/x"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.Embed, "/x"));
    }

    [Fact]
    public void Setup_is_doctor_and_ignores_the_folder()
    {
        string[] expected = ["doctor"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.Setup, null));
    }

    [Fact]
    public void No_mode_ever_includes_the_progress_flag()
    {
        foreach (var kind in Enum.GetValues<WorkspaceModeKind>())
        {
            Assert.DoesNotContain("--progress", CommandBuilder.Build(kind, "/x"));
        }
    }
}
