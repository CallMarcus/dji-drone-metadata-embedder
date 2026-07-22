using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceModeTests
{
    [Fact]
    public void Catalogue_has_the_six_modes_in_strip_order() =>
        Assert.Equal(
            [
                WorkspaceModeKind.FlightMap, WorkspaceModeKind.PhotoMap,
                WorkspaceModeKind.Embed, WorkspaceModeKind.Convert,
                WorkspaceModeKind.Verify, WorkspaceModeKind.Setup,
            ],
            WorkspaceMode.All.Select(m => m.Kind));

    [Fact]
    public void Verify_accepts_both_source_kinds() =>
        Assert.Equal(SourceKinds.Folder | SourceKinds.File,
            WorkspaceMode.Of(WorkspaceModeKind.Verify).Sources);

    [Fact]
    public void Sources_match_each_modes_reach()
    {
        Assert.All(WorkspaceMode.All, m => Assert.Equal(m.Kind switch
        {
            WorkspaceModeKind.Setup => SourceKinds.None,
            WorkspaceModeKind.Convert or WorkspaceModeKind.Verify =>
                SourceKinds.Folder | SourceKinds.File,
            _ => SourceKinds.Folder,
        }, m.Sources));
    }

    [Fact]
    public void Of_finds_each_mode()
    {
        Assert.Equal("Flight map",
            WorkspaceMode.Of(WorkspaceModeKind.FlightMap).Title);
    }
}
