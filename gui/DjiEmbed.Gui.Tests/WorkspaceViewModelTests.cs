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

    // The REAL default probe is true on Windows, so a map-run test built
    // without an explicit probe would spawn `serve` children on a Windows
    // dev machine — pin probe=false and a fake server so every test is
    // deterministic on every OS.
    private static WorkspaceViewModel Vm(
        string? cli, Func<string?>? cliResolver = null,
        IMapServer? mapServer = null, Func<bool>? previewAvailable = null) =>
        new(cli, new DjiEmbedRunner(), mapServer ?? new FakeMapServer(null),
            () => { }, cliResolver,
            previewAvailable ?? (static () => false));

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

    private static readonly string[] DoctorStream =
    [
        """{"v": 1, "event": "start", "command": "doctor"}""",
        """{"v": 1, "event": "result", "ok": true, "outputs": [], "summary": {"tools": {"ffmpeg": {"present": true, "version": "7.1"}}}}""",
    ];

    [Fact]
    public async Task Missing_cli_fails_with_novice_wording()
    {
        var vm = Vm(null);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("engine", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Missing_cli_reprobes_via_resolver_and_recovers()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["doctor"] = (DoctorStream, 0),
        });
        var vm = Vm(null, cliResolver: () => cli);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
    }

    [Fact]
    public async Task Missing_cli_without_resolver_still_fails_cleanly()
    {
        var vm = Vm(null, cliResolver: null);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
    }

    [Fact]
    public async Task Flight_map_mode_runs_flightmap_recursively()
    {
        var argsFile = Path.Combine(_dir, "args-fm.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile, FlightmapStream);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal(["flightmap.html"], vm.Outputs);
        var argv = File.ReadAllText(argsFile);
        Assert.StartsWith("flightmap", argv.TrimStart());
        Assert.Contains("-r", argv);
    }

    [Fact]
    public async Task Photo_map_mode_links_originals_for_the_pano_viewer()
    {
        // #305: without --link-originals the map has no pano viewer at all.
        var argsFile = Path.Combine(_dir, "args-pm.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile, PhotomapStream);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(photos: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Contains("--link-originals", File.ReadAllText(argsFile));
    }

    [Fact]
    public async Task Wrong_content_for_the_mode_fails_before_launching_anything()
    {
        // A CLI path that would explode if executed proves nothing ran.
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(photos: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.FlightMap);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("folder", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Setup_mode_parses_the_doctor_checklist()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["doctor"] = (DoctorStream, 0),
        });
        var vm = Vm(cli);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.True(vm.AllGood);
        var item = Assert.Single(vm.SetupItems);
        Assert.Equal("Video tools (FFmpeg)", item.Label);
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
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("GPS telemetry", vm.ErrorMessage);
        Assert.Contains("detail line", vm.ErrorDetails);
    }

    [Fact]
    public async Task Cancel_returns_to_the_idle_pane()
    {
        var cli = FakeCli.WriteEventStream(_dir,
            ["""{"v": 1, "event": "start", "command": "flightmap"}"""],
            sleepSeconds: 30);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        var run = vm.RunCommand.ExecuteAsync(null);
        while (vm.Step != FlowStep.Running)
        {
            await Task.Delay(20, TestContext.Current.CancellationToken);
        }
        vm.CancelCommand.Execute(null);
        await run;
        Assert.Equal(FlowStep.Pick, vm.Step);
    }

    [Fact]
    public async Task Process_another_resets_to_idle_keeping_the_folder()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli);
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        vm.GoHomeCommand.Execute(null);
        Assert.Equal(FlowStep.Pick, vm.Step);
        Assert.Equal(folder, vm.SelectedFolder);
    }

    [Fact]
    public async Task Map_run_after_setup_shows_no_stale_checklist_state()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["doctor"] = (DoctorStream, 0),
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.True(vm.AllGood);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Empty(vm.SetupItems);
        Assert.False(vm.AllGood);
        Assert.Equal(["flightmap.html"], vm.Outputs);
    }

    [Fact]
    public async Task Second_run_replaces_outputs_instead_of_appending()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        vm.GoHomeCommand.Execute(null);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal(["flightmap.html"], vm.Outputs);
    }

    // The switch in RunAsync gives Embed mode its own wrong-content message
    // and its own args — neither is exercised above (those tests all drive
    // FlightMap/PhotoMap), so cover them explicitly here.
    [Fact]
    public async Task Embed_mode_without_videos_fails_before_launching_anything()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("video", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Embed_mode_runs_embed_and_reports_done_with_outputs()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "progress", "current": 1, "total": 1, "item": "DJI_0001.MP4"}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": ["/footage/processed"], "summary": {"processed": 1}}""",
        ]);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(videos: true));
        Assert.Equal(WorkspaceModeKind.Embed, vm.SelectedMode.Kind);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal(["/footage/processed"], vm.Outputs);
    }

    // RunSetupAsync has its own success/failure handling, separate from the
    // shared RunStepAsync path the map/embed modes use above — cover its
    // ok:false-but-exit-0 (red checklist item) and crashed-exit branches.
    [Fact]
    public async Task Setup_mode_missing_tool_still_lands_on_done_with_a_red_item()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "doctor"}""",
            """{"v": 1, "event": "warning", "message": "Not found", "item": "ffmpeg"}""",
            """{"v": 1, "event": "result", "ok": false, "outputs": [], "summary": {"ok": false, "tools": {"ffmpeg": {"present": false}, "exiftool": {"present": true}}, "system": {}}}""",
        ]);
        var vm = Vm(cli);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.False(vm.AllGood);
        var ffmpeg = Assert.Single(vm.SetupItems, i => i.Label.Contains("FFmpeg"));
        Assert.False(ffmpeg.Present);
    }

    [Fact]
    public async Task Setup_mode_crashed_doctor_lands_on_failed()
    {
        var cli = FakeCli.WriteEventStream(_dir,
            ["""{"v": 1, "event": "start", "command": "doctor"}"""],
            exitCode: 3, stderrLine: "Traceback");
        var vm = Vm(cli);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("Traceback", vm.ErrorDetails);
    }

    [Fact]
    public async Task Partial_failure_ok_false_lands_on_failed_with_details()
    {
        // Embed contract nuance: per-file failures are exit 0 + result ok:false
        // with no message — Fail() must fall back to the mode's generic copy.
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "result", "ok": false, "outputs": [], "summary": {}}""",
        ], exitCode: 0, stderrLine: "boom detail");
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(videos: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal("Something went wrong while embedding the flight data.",
            vm.ErrorMessage);
        Assert.Contains("boom detail", vm.ErrorDetails);
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
                sawRunning = vm.Step == FlowStep.Running;
            }
        };
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.True(sawRunning, "expected a progress item while running");
        Assert.Equal(1, vm.Current);
        Assert.Equal(1, vm.Total);
    }
}
