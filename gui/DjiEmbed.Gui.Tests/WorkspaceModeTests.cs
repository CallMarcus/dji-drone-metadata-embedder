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
    public void Folder_modes_take_folders_setup_takes_nothing()
    {
        Assert.All(WorkspaceMode.All, m => Assert.Equal(
            m.Kind == WorkspaceModeKind.Setup ? SourceKinds.None : SourceKinds.Folder,
            m.Sources));
    }

    [Fact]
    public void Of_finds_each_mode()
    {
        Assert.Equal("Flight map",
            WorkspaceMode.Of(WorkspaceModeKind.FlightMap).Title);
    }
}
