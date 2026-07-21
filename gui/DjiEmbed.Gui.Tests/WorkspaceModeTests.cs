using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceModeTests
{
    [Fact]
    public void Catalogue_has_the_five_m1_plus_m4a_modes_in_strip_order()
    {
        Assert.Equal(
            [WorkspaceModeKind.FlightMap, WorkspaceModeKind.PhotoMap,
             WorkspaceModeKind.Embed, WorkspaceModeKind.Convert,
             WorkspaceModeKind.Setup],
            WorkspaceMode.All.Select(m => m.Kind).ToArray());
    }

    [Fact]
    public void Sources_match_each_modes_reach()
    {
        Assert.All(WorkspaceMode.All, m => Assert.Equal(m.Kind switch
        {
            WorkspaceModeKind.Setup => SourceKinds.None,
            WorkspaceModeKind.Convert => SourceKinds.Folder | SourceKinds.File,
            _ => SourceKinds.Folder,
        }, m.Sources));
    }

    [Fact]
    public void Convert_sits_between_embed_and_setup_in_the_strip()
    {
        var kinds = WorkspaceMode.All.Select(m => m.Kind).ToArray();
        Assert.Equal([WorkspaceModeKind.FlightMap, WorkspaceModeKind.PhotoMap,
            WorkspaceModeKind.Embed, WorkspaceModeKind.Convert,
            WorkspaceModeKind.Setup], kinds);
    }

    [Fact]
    public void Of_finds_each_mode()
    {
        Assert.Equal("Flight map",
            WorkspaceMode.Of(WorkspaceModeKind.FlightMap).Title);
    }
}
