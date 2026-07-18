using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceModeTests
{
    [Fact]
    public void Catalogue_has_the_four_m1_modes_in_strip_order()
    {
        Assert.Equal(
            [WorkspaceModeKind.FlightMap, WorkspaceModeKind.PhotoMap,
             WorkspaceModeKind.Embed, WorkspaceModeKind.Setup],
            WorkspaceMode.All.Select(m => m.Kind).ToArray());
    }

    [Fact]
    public void Only_setup_runs_without_a_folder()
    {
        Assert.All(WorkspaceMode.All, m =>
            Assert.Equal(m.Kind != WorkspaceModeKind.Setup, m.NeedsFolder));
    }

    [Fact]
    public void Of_finds_each_mode()
    {
        Assert.Equal("Flight map",
            WorkspaceMode.Of(WorkspaceModeKind.FlightMap).Title);
    }
}
