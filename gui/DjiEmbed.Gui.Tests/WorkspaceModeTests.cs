using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceModeTests
{
    [Fact]
    public void Catalogue_has_the_seven_modes_in_strip_order() =>
        Assert.Equal(
            [
                WorkspaceModeKind.FlightMap, WorkspaceModeKind.PhotoMap,
                WorkspaceModeKind.Embed, WorkspaceModeKind.Convert,
                WorkspaceModeKind.Verify, WorkspaceModeKind.PanoEdit,
                WorkspaceModeKind.Setup,
            ],
            WorkspaceMode.All.Select(m => m.Kind));

    // #476: what a mode needs from a folder is carried by the mode, so a
    // new entry cannot compile without answering it — a switch elsewhere
    // would quietly answer "nothing fits" and override the user's choice.
    [Fact]
    public void Every_folder_mode_declares_what_it_needs() =>
        Assert.All(WorkspaceMode.All, m => Assert.Equal(
            m.Sources.HasFlag(SourceKinds.Folder),
            m.Needs != MediaKinds.None));

    [Fact]
    public void Fits_is_answered_from_the_folder_contents()
    {
        var photosOnly = new FolderContents(
            false, true, false, false, true, false, null, null);
        Assert.True(WorkspaceMode.Of(WorkspaceModeKind.PanoEdit).Fits(photosOnly));
        Assert.True(WorkspaceMode.Of(WorkspaceModeKind.PhotoMap).Fits(photosOnly));
        Assert.True(WorkspaceMode.Of(WorkspaceModeKind.Verify).Fits(photosOnly));
        Assert.False(WorkspaceMode.Of(WorkspaceModeKind.Convert).Fits(photosOnly));
        Assert.False(WorkspaceMode.Of(WorkspaceModeKind.FlightMap).Fits(photosOnly));
        // Setup takes no source at all, so nothing ever fits it.
        Assert.False(WorkspaceMode.Of(WorkspaceModeKind.Setup).Fits(photosOnly));
    }

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
