using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class EmbedTelemetryViewModelTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-embedvm-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string MakeFolder(bool videos = false, bool srt = false)
    {
        var folder = Path.Combine(_dir, "footage");
        Directory.CreateDirectory(folder);
        if (videos) File.WriteAllText(Path.Combine(folder, "DJI_0001.MP4"), "");
        if (srt) File.WriteAllText(Path.Combine(folder, "DJI_0001.SRT"), "");
        return folder;
    }

    private static EmbedTelemetryViewModel Vm(string? cli) =>
        new(cli, new DjiEmbedRunner(), () => { });

    [Fact]
    public async Task Folder_without_videos_fails_before_launching_anything()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.StartCommand.ExecuteAsync(MakeFolder(srt: true));
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("video", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Happy_embed_reports_done_with_output_folder()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "progress", "current": 1, "total": 1, "item": "DJI_0001.MP4"}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": ["/footage/processed"], "summary": {"processed": 1}}""",
        ]);
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(MakeFolder(videos: true, srt: true));
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal(["/footage/processed"], vm.Outputs);
    }

    [Fact]
    public async Task Partial_failure_ok_false_lands_on_failed_with_details()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 2}""",
            """{"v": 1, "event": "result", "ok": false, "outputs": ["/footage/processed"], "summary": {"errors": ["DJI_0002.MP4"]}}""",
        ], stderrLine: "ffmpeg exploded");
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(MakeFolder(videos: true, srt: true));
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("ffmpeg exploded", vm.ErrorDetails);
    }
}
