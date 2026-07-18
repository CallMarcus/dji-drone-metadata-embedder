using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceViewModelTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-workspace-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string MakeFolder(
        bool srt = false, bool photos = false, bool videos = false)
    {
        var folder = Path.Combine(_dir, "footage-" + Guid.NewGuid().ToString("N")[..6]);
        Directory.CreateDirectory(folder);
        if (srt) File.WriteAllText(Path.Combine(folder, "DJI_0001.SRT"), "");
        if (photos) File.WriteAllText(Path.Combine(folder, "IMG_1.JPG"), "");
        if (videos) File.WriteAllText(Path.Combine(folder, "DJI_0001.MP4"), "");
        return folder;
    }

    private static WorkspaceViewModel Vm(string? cli) =>
        new(cli, new DjiEmbedRunner(), new MapServer(), () => { });

    [Fact]
    public void Starts_idle_with_flight_map_selected_and_no_folder()
    {
        var vm = Vm("unused");
        Assert.Equal(FlowStep.Pick, vm.Step);
        Assert.Equal(WorkspaceModeKind.FlightMap, vm.SelectedMode.Kind);
        Assert.Null(vm.SelectedFolder);
    }

    [Fact]
    public void Setup_mode_can_run_without_a_folder_others_cannot()
    {
        var vm = Vm("unused");
        Assert.False(vm.CanRun);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        Assert.True(vm.CanRun);
    }

    [Fact]
    public async Task Dropping_flight_logs_suggests_and_selects_flight_map()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true, photos: true));
        Assert.Equal(WorkspaceModeKind.FlightMap, vm.SuggestedMode!.Kind);
        Assert.Equal(WorkspaceModeKind.FlightMap, vm.SelectedMode.Kind);
        Assert.True(vm.CanRun);
    }

    [Fact]
    public async Task Photos_only_suggests_photo_map()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.Equal(WorkspaceModeKind.PhotoMap, vm.SuggestedMode!.Kind);
        Assert.Equal(WorkspaceModeKind.PhotoMap, vm.SelectedMode.Kind);
    }

    [Fact]
    public async Task Videos_only_suggests_embed()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(videos: true));
        Assert.Equal(WorkspaceModeKind.Embed, vm.SuggestedMode!.Kind);
    }

    [Fact]
    public async Task Empty_folder_suggests_nothing_and_keeps_selection()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        await vm.SetFolderAsync(MakeFolder());
        Assert.Null(vm.SuggestedMode);
        Assert.Equal(WorkspaceModeKind.Embed, vm.SelectedMode.Kind);
    }

    [Fact]
    public async Task Clear_folder_resets_source_and_suggestion()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.ClearFolderCommand.Execute(null);
        Assert.Null(vm.SelectedFolder);
        Assert.Null(vm.SuggestedMode);
        Assert.False(vm.CanRun);
    }

    [Fact]
    public async Task New_folder_after_done_returns_to_idle_and_reselects()
    {
        var vm = Vm("unused");
        vm.Step = FlowStep.Done;
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.Equal(FlowStep.Pick, vm.Step);
        Assert.Equal(WorkspaceModeKind.PhotoMap, vm.SelectedMode.Kind);
    }

    [Fact]
    public async Task Folder_drop_while_running_is_ignored()
    {
        var vm = Vm("unused");
        vm.Step = FlowStep.Running;
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.Null(vm.SelectedFolder);
        Assert.Equal(FlowStep.Running, vm.Step);
    }
}
