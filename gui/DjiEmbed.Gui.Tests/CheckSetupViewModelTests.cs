using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class CheckSetupViewModelTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-checkvm-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private static CheckSetupViewModel Vm(string? cli) =>
        new(cli, new DjiEmbedRunner(), () => { });

    private const string AllGoodResult =
        """{"v": 1, "event": "result", "ok": true, "outputs": [], "summary": {"ok": true, "tools": {"ffmpeg": {"present": true}, "exiftool": {"present": true, "version": "13.30"}}, "system": {}}}""";

    [Fact]
    public async Task All_tools_present_shows_green_checklist()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "doctor"}""",
            AllGoodResult,
        ]);
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.True(vm.AllGood);
        Assert.Equal(2, vm.Items.Count);
        var exif = Assert.Single(vm.Items, i => i.Label.Contains("ExifTool"));
        Assert.True(exif.Present);
        Assert.Contains("13.30", exif.Detail);
    }

    [Fact]
    public async Task Missing_tool_still_lands_on_done_with_a_red_item()
    {
        // Missing dependencies are a report, not a crash (mirrors the CLI's
        // ok=false + exit 0 rule) — the checklist is the result screen.
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "doctor"}""",
            """{"v": 1, "event": "warning", "message": "Not found", "item": "ffmpeg"}""",
            """{"v": 1, "event": "result", "ok": false, "outputs": [], "summary": {"ok": false, "tools": {"ffmpeg": {"present": false}, "exiftool": {"present": true}}, "system": {}}}""",
        ]);
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.False(vm.AllGood);
        var ffmpeg = Assert.Single(vm.Items, i => i.Label.Contains("FFmpeg"));
        Assert.False(ffmpeg.Present);
    }

    [Fact]
    public async Task Missing_cli_fails_with_novice_wording()
    {
        var vm = Vm(null);
        await vm.StartCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("engine", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Crashed_doctor_lands_on_failed()
    {
        var cli = FakeCli.WriteEventStream(_dir,
            ["""{"v": 1, "event": "start", "command": "doctor"}"""],
            exitCode: 3, stderrLine: "Traceback");
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("Traceback", vm.ErrorDetails);
    }
}
