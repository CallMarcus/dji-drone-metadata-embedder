using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class MakeMapViewModelTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-makemap-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string MakeFolder(bool srt = false, bool photos = false)
    {
        var folder = Path.Combine(_dir, "footage");
        Directory.CreateDirectory(folder);
        if (srt) File.WriteAllText(Path.Combine(folder, "DJI_0001.SRT"), "");
        if (photos) File.WriteAllText(Path.Combine(folder, "IMG_1.JPG"), "");
        return folder;
    }

    private static readonly string[] FlightmapStream =
    [
        """{"v": 1, "event": "start", "command": "flightmap", "total": 1}""",
        """{"v": 1, "event": "progress", "current": 1, "total": 1, "item": "DJI_0001.SRT"}""",
        """{"v": 1, "event": "result", "ok": true, "outputs": ["flightmap.html"], "summary": {}}""",
    ];

    private static readonly string[] PhotomapStream =
    [
        """{"v": 1, "event": "start", "command": "photomap", "total": 1}""",
        """{"v": 1, "event": "result", "ok": true, "outputs": ["photomap.html"], "summary": {}}""",
    ];

    private static MakeMapViewModel Vm(string? cli, bool wentHome = false) =>
        new(cli, new DjiEmbedRunner(), () => { });

    [Fact]
    public void Starts_on_the_pick_step()
    {
        Assert.Equal(MakeMapStep.Pick, Vm("unused").Step);
    }

    [Fact]
    public async Task Missing_cli_fails_with_novice_wording()
    {
        var vm = Vm(null);
        await vm.StartCommand.ExecuteAsync(MakeFolder(srt: true));
        Assert.Equal(MakeMapStep.Failed, vm.Step);
        Assert.Contains("engine", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Folder_without_footage_fails_before_launching_anything()
    {
        // A CLI path that would explode if executed proves nothing ran.
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.StartCommand.ExecuteAsync(MakeFolder());
        Assert.Equal(MakeMapStep.Failed, vm.Step);
        Assert.Contains("folder", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Flight_logs_only_runs_flightmap_and_reports_done()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(MakeFolder(srt: true));
        Assert.Equal(MakeMapStep.Done, vm.Step);
        Assert.Equal(["flightmap.html"], vm.Outputs);
    }

    [Fact]
    public async Task Mixed_folder_runs_both_commands_and_collects_all_outputs()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
            ["photomap"] = (PhotomapStream, 0),
        });
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(MakeFolder(srt: true, photos: true));
        Assert.Equal(MakeMapStep.Done, vm.Step);
        Assert.Equal(["flightmap.html", "photomap.html"], vm.Outputs);
    }

    [Fact]
    public async Task Cli_error_shows_its_message_and_stderr_details()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "flightmap"}""",
            """{"v": 1, "event": "error", "message": "None of the 3 SRT files contain GPS telemetry"}""",
        ], exitCode: 1, stderrLine: "detail line");
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(MakeFolder(srt: true));
        Assert.Equal(MakeMapStep.Failed, vm.Step);
        Assert.Contains("GPS telemetry", vm.ErrorMessage);
        Assert.Contains("detail line", vm.ErrorDetails);
    }

    [Fact]
    public async Task Progress_events_update_the_running_state()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli);
        var sawRunning = false;
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName == nameof(vm.CurrentItem) && vm.CurrentItem is not null)
            {
                sawRunning = vm.Step == MakeMapStep.Running;
            }
        };
        await vm.StartCommand.ExecuteAsync(MakeFolder(srt: true));
        Assert.True(sawRunning, "expected a progress item while running");
        Assert.Equal(1, vm.Current);
        Assert.Equal(1, vm.Total);
    }

    [Fact]
    public async Task Cancel_returns_to_the_pick_step()
    {
        var cli = FakeCli.WriteEventStream(_dir,
            ["""{"v": 1, "event": "start", "command": "flightmap"}"""],
            sleepSeconds: 30);
        var vm = Vm(cli);
        var run = vm.StartCommand.ExecuteAsync(MakeFolder(srt: true));
        while (vm.Step != MakeMapStep.Running)
        {
            await Task.Delay(20, TestContext.Current.CancellationToken);
        }
        vm.CancelCommand.Execute(null);
        await run;
        Assert.Equal(MakeMapStep.Pick, vm.Step);
    }
}
