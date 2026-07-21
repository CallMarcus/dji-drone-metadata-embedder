using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceViewModelTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-workspace-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string MakeFolder(
        bool srt = false, bool photos = false, bool videos = false,
        bool flightMap = false, bool photoMap = false,
        bool nestedSrt = false, bool nestedPhotos = false,
        bool nestedVideos = false)
    {
        var folder = Path.Combine(_dir, "footage-" + Guid.NewGuid().ToString("N")[..6]);
        Directory.CreateDirectory(folder);
        if (srt) File.WriteAllText(Path.Combine(folder, "DJI_0001.SRT"), "");
        if (photos) File.WriteAllText(Path.Combine(folder, "IMG_1.JPG"), "");
        if (videos) File.WriteAllText(Path.Combine(folder, "DJI_0001.MP4"), "");
        if (flightMap) File.WriteAllText(Path.Combine(folder, "flightmap.html"), "");
        if (photoMap) File.WriteAllText(Path.Combine(folder, "photomap.html"), "");
        if (nestedSrt || nestedPhotos || nestedVideos)
        {
            var sub = Directory.CreateDirectory(
                Path.Combine(folder, "trip")).FullName;
            if (nestedSrt) File.WriteAllText(Path.Combine(sub, "DJI_0002.SRT"), "");
            if (nestedPhotos) File.WriteAllText(Path.Combine(sub, "IMG_2.JPG"), "");
            if (nestedVideos) File.WriteAllText(Path.Combine(sub, "DJI_0002.MP4"), "");
        }
        return folder;
    }

    // The REAL default probe is true on Windows, so a map-run test built
    // without an explicit probe would spawn `serve` children on a Windows
    // dev machine — pin probe=false and a fake server so every test is
    // deterministic on every OS.
    private static WorkspaceViewModel Vm(
        string? cli, Func<string?>? cliResolver = null,
        IMapServer? mapServer = null, Func<bool>? previewAvailable = null,
        Func<string, FolderContents>? folderInspector = null) =>
        new(cli, new DjiEmbedRunner(), mapServer ?? new FakeMapServer(null),
            () => { }, cliResolver,
            previewAvailable ?? (static () => false),
            folderInspector);

    private static FolderContents Contents(
        bool logs = false, bool photos = false, bool videos = false,
        bool topLogs = false, bool topPhotos = false, bool topVideos = false) =>
        new(logs, photos, videos, topLogs, topPhotos, topVideos, null, null);

    [Fact]
    public async Task Folder_scans_go_through_the_injected_inspector()
    {
        var inspected = new List<string>();
        var vm = Vm(Path.Combine(_dir, "does-not-exist"), folderInspector: dir =>
        {
            inspected.Add(dir);
            return Contents(photos: true, topPhotos: true);
        });
        await vm.SetFolderAsync("Z:/nowhere");           // scan site 1
        await vm.RunCommand.ExecuteAsync(null);          // scan site 2
        Assert.Equal(["Z:/nowhere", "Z:/nowhere"], inspected);
    }

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
        vm.ClearSourceCommand.Execute(null);
        Assert.Null(vm.SelectedFolder);
        Assert.Null(vm.SuggestedMode);
        Assert.False(vm.CanRun);
    }

    // M4a Task 2: SOURCE learns to hold a single file instead of a folder,
    // mutually exclusive with it.
    [Fact]
    public async Task Picking_a_file_clears_the_folder_and_vice_versa()
    {
        var vm = Vm("unused",
            folderInspector: _ => Contents(logs: true, topLogs: true));
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.Equal("C:/clips/DJI_0001.SRT", vm.SelectedFile);
        Assert.Null(vm.SelectedFolder);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        Assert.Null(vm.SelectedFile);
        Assert.NotNull(vm.SelectedFolder);
        vm.SetFile("C:/clips/DJI_0002.SRT");
        Assert.Equal("C:/clips/DJI_0002.SRT", vm.SelectedFile);
        Assert.Null(vm.SelectedFolder);
    }

    [Fact]
    public void File_pick_suggests_and_selects_convert_mode()
    {
        var vm = Vm("unused");
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.Equal(WorkspaceModeKind.Convert, vm.SelectedMode.Kind);
        Assert.Equal(WorkspaceModeKind.Convert, vm.SuggestedMode!.Kind);
    }

    [Fact]
    public void Convert_strip_previews_batch_for_folders_and_bare_for_files()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        Assert.Equal("dji-embed convert gpx <folder> -b", vm.CommandPreview);
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.Equal("dji-embed convert gpx C:/clips/DJI_0001.SRT",
            vm.CommandPreview);
    }

    [Fact]
    public void Convert_options_repaint_the_strip()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        vm.ConvertOptions.SelectedFormat = vm.ConvertOptions.Formats
            .First(f => f.Key == "kml");
        Assert.Contains("convert kml", vm.CommandPreview);
    }

    [Fact]
    public void Source_changes_clear_the_convert_output_override_too()
    {
        var vm = Vm("unused",
            folderInspector: _ => Contents(logs: true, topLogs: true));
        vm.ConvertOptions.Output = "C:/elsewhere/track.gpx";
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.Equal("", vm.ConvertOptions.Output);
    }

    [Fact]
    public void Clear_source_removes_a_file_too()
    {
        var vm = Vm("unused");
        vm.SetFile("C:/clips/DJI_0001.SRT");
        vm.ClearSourceCommand.Execute(null);
        Assert.Null(vm.SelectedFile);
        Assert.Equal(FlowStep.Pick, vm.Step);
    }

    [Fact]
    public async Task Source_display_shows_folder_path_but_file_name_only()
    {
        var vm = Vm("unused");
        Assert.Null(vm.SourceDisplay);
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.Equal("DJI_0001.SRT", vm.SourceDisplay);
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);
        Assert.Equal(folder, vm.SourceDisplay);
    }

    [Fact]
    public void File_pick_enables_the_run_button()
    {
        var vm = Vm("unused");
        Assert.False(vm.CanRun);
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.True(vm.CanRun);
    }

    [Fact]
    public async Task File_pick_is_inert_while_busy()
    {
        // Same discipline as SetFolderAsync: a run owns its inputs (#340).
        // Copies the gated-scan idiom from The_whole_run_is_busy_from_its_first_line.
        var cli = FakeCli.WriteEventStream(_dir, FlightmapStream);
        Func<string, FolderContents> inspect =
            _ => Contents(logs: true, topLogs: true);
        var vm = Vm(cli, folderInspector: dir => inspect(dir));
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);

        var gate = new TaskCompletionSource();
        inspect = _ =>
        {
            gate.Task.Wait();
            return Contents(logs: true, topLogs: true);
        };
        var run = vm.RunCommand.ExecuteAsync(null);

        Assert.True(vm.IsBusy);
        vm.SetFile("C:/clips/DJI_0001.SRT");
        Assert.Null(vm.SelectedFile);      // inert while busy

        gate.SetResult();
        await run;
        Assert.False(vm.IsBusy);
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
    public async Task Folder_drop_during_a_run_is_ignored()
    {
        var cli = FakeCli.WriteEventStream(_dir, FlightmapStream);
        Func<string, FolderContents> inspect =
            _ => Contents(logs: true, topLogs: true);
        var vm = Vm(cli, folderInspector: dir => inspect(dir));
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);
        var gate = new TaskCompletionSource();
        inspect = _ =>
        {
            gate.Task.Wait();
            return Contents(logs: true, topLogs: true);
        };
        var run = vm.RunCommand.ExecuteAsync(null);

        await vm.SetFolderAsync(MakeFolder(photos: true));

        Assert.Equal(folder, vm.SelectedFolder);
        gate.SetResult();
        await run;
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

    private static readonly string[] ConvertStream =
    [
        """{"v": 1, "event": "start", "command": "convert", "total": 1}""",
        """{"v": 1, "event": "progress", "current": 1, "total": 1, "item": "DJI_0001.SRT"}""",
        """{"v": 1, "event": "result", "ok": true, "outputs": ["DJI_0001.gpx"], "summary": {"converted": 1, "skipped": 0, "format": "gpx"}}""",
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

    // #333/#338: the folder scan is recursive, but embed reads one level
    // and the map commands recurse only with -r. When the media is out of
    // the selected command's reach the run must not start, and the message
    // must speak GUI ("Include subfolders"), not CLI ("-r").
    [Fact]
    public async Task Flight_map_without_subfolders_blocks_nested_only_logs_with_guidance()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(nestedSrt: true));
        vm.FlightOptions.Recursive = false;
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal(
            "Those flight logs are in subfolders — turn on Include subfolders.",
            vm.ErrorMessage);
    }

    [Fact]
    public async Task Photo_map_without_subfolders_blocks_nested_only_photos_with_guidance()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(nestedPhotos: true));
        vm.PhotoOptions.Recursive = false;
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal(
            "Those photos are in subfolders — turn on Include subfolders.",
            vm.ErrorMessage);
    }

    [Fact]
    public async Task Embed_blocks_nested_only_videos_instead_of_a_hollow_success()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(nestedVideos: true));  // suggests Embed
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal(
            "The videos are in subfolders, and Embed reads only the folder "
            + "you pick — pick the subfolder that holds the videos.",
            vm.ErrorMessage);
    }

    [Fact]
    public async Task Not_found_message_drops_the_subfolders_clause_when_the_toggle_is_off()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(photos: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.FlightMap);
        vm.FlightOptions.Recursive = false;
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.DoesNotContain("subfolders are included", vm.ErrorMessage);
    }

    [Fact]
    public async Task Not_found_message_keeps_the_subfolders_clause_when_the_toggle_is_on()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(photos: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.FlightMap);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("subfolders are included automatically", vm.ErrorMessage);
    }

    // Positive control for the new guards: top-level media with the toggle
    // off is within reach, so the run proceeds (and stays non-recursive).
    [Fact]
    public async Task Flight_map_without_subfolders_still_runs_on_top_level_logs()
    {
        var argsFile = Path.Combine(_dir, "args-fm-toponly.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile, FlightmapStream);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(srt: true, nestedSrt: true));
        vm.FlightOptions.Recursive = false;
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        var argv = File.ReadAllLines(argsFile);
        Assert.Equal("flightmap", argv[0]);
        Assert.DoesNotContain("-r", argv);
    }

    // #340: the run's folder scan happens before ExecuteFlowAsync sets
    // Step = Running, and that window used to leave every guard open. A
    // run is busy from its first line, and it owns the inputs it captured.
    [Fact]
    public async Task The_whole_run_is_busy_from_its_first_line()
    {
        var cli = FakeCli.WriteEventStream(_dir, FlightmapStream);
        Func<string, FolderContents> inspect =
            _ => Contents(logs: true, topLogs: true);
        var vm = Vm(cli, folderInspector: dir => inspect(dir));
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);

        var gate = new TaskCompletionSource();
        inspect = _ =>
        {
            gate.Task.Wait();
            return Contents(logs: true, topLogs: true);
        };
        var run = vm.RunCommand.ExecuteAsync(null);

        Assert.True(vm.IsBusy);
        vm.ClearSourceCommand.Execute(null);
        Assert.Equal(folder, vm.SelectedFolder);      // inert while busy
        await vm.SetFolderAsync("Z:/other");
        Assert.Equal(folder, vm.SelectedFolder);      // inert while busy
        Assert.False(vm.OpenExistingMapCommand.CanExecute(null));

        gate.SetResult();
        await run;
        Assert.False(vm.IsBusy);
        Assert.Equal(FlowStep.Done, vm.Step);
    }

    [Fact]
    public async Task Mid_scan_edits_do_not_alter_the_executed_argv()
    {
        var argsFile = Path.Combine(_dir, "args-midscan.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile, FlightmapStream);
        Func<string, FolderContents> inspect =
            _ => Contents(logs: true, topLogs: true);
        var vm = Vm(cli, folderInspector: dir => inspect(dir));
        await vm.SetFolderAsync(MakeFolder(srt: true));

        var gate = new TaskCompletionSource();
        inspect = _ =>
        {
            gate.Task.Wait();
            return Contents(logs: true, topLogs: true);
        };
        var run = vm.RunCommand.ExecuteAsync(null);
        // The strip promised `flightmap <folder> -r` at press time; these
        // edits arrive while the scan is still in flight.
        vm.FlightOptions.Recursive = false;
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        gate.SetResult();
        await run;

        var argv = File.ReadAllLines(argsFile);
        Assert.Equal("flightmap", argv[0]);
        Assert.Contains("-r", argv);
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

    // The mirror guard: the test above covers flightmap-on-photos, this one
    // photomap-on-videos — the only wrong-content arm that had no test.
    [Fact]
    public async Task Photo_map_on_a_videos_folder_fails_before_launching_anything()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(videos: true));   // suggests Embed
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Contains("photos", vm.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    // M4a Task 7: Convert runs bare on a single file, batch on a folder,
    // and guards a folder whose media is out of -b's one-level reach the
    // same way embed does (#333/#338).
    [Fact]
    public async Task Convert_runs_bare_on_a_single_file()
    {
        var argsFile = Path.Combine(_dir, "args-convert-file.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile, ConvertStream);
        var vm = Vm(cli);
        var srt = Path.Combine(MakeFolder(srt: true), "DJI_0001.SRT");
        vm.SetFile(srt);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        var argv = File.ReadAllLines(argsFile);
        Assert.Equal(["convert", "gpx", srt], argv[..3]);
        Assert.DoesNotContain("-b", argv);
    }

    [Fact]
    public async Task Convert_runs_batch_on_a_folder()
    {
        var argsFile = Path.Combine(_dir, "args-convert-folder.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile, ConvertStream);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Contains("-b", File.ReadAllLines(argsFile));
    }

    [Fact]
    public async Task Convert_blocks_a_folder_whose_media_is_nested_with_guidance()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(nestedSrt: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal(
            "Those files are in subfolders — Convert reads only the folder "
            + "you pick. Pick the subfolder that holds the flight logs or "
            + "videos.",
            vm.ErrorMessage);
    }

    [Fact]
    public async Task Convert_blocks_an_empty_folder_with_guidance()
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        await vm.SetFolderAsync(MakeFolder(photos: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal(
            "No flight logs (.SRT) or drone videos were found in that "
            + "folder. Pick the folder that holds the footage to convert.",
            vm.ErrorMessage);
    }

    [Theory]
    [InlineData(WorkspaceModeKind.FlightMap,
        "Flight map works on a folder of footage — pick the folder that "
        + "holds your flights, not a single file.")]
    [InlineData(WorkspaceModeKind.PhotoMap,
        "Photo map works on a folder of pictures — pick the folder that "
        + "holds your photos, not a single file.")]
    [InlineData(WorkspaceModeKind.Embed,
        "Embed telemetry works on a folder of videos with their .SRT "
        + "flight logs — pick that folder, not a single file.")]
    public async Task Folder_modes_block_a_file_source_with_guidance(
        WorkspaceModeKind kind, string message)
    {
        var vm = Vm(Path.Combine(_dir, "does-not-exist"));
        vm.SetFile("C:/clips/DJI_0001.SRT");
        vm.SelectedMode = WorkspaceMode.Of(kind);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Equal(message, vm.ErrorMessage);
    }

    [Fact]
    public async Task Convert_html_file_run_primes_the_inline_preview()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "convert", "total": 1}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": ["DJI_0001.html"], "summary": {"converted": 1, "skipped": 0, "format": "html"}}""",
        ]);
        var server = new FakeMapServer("http://127.0.0.1:8/DJI_0001.html");
        var vm = Vm(cli, mapServer: server, previewAvailable: static () => true);
        var srt = Path.Combine(MakeFolder(srt: true), "DJI_0001.SRT");
        vm.SetFile(srt);
        vm.ConvertOptions.SelectedFormat = vm.ConvertOptions.Formats
            .First(f => f.Key == "html");
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.NotNull(vm.PreviewUrl);
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

    [Fact]
    public async Task Map_done_primes_the_inline_preview()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var server = new FakeMapServer("http://127.0.0.1:8/flightmap.html");
        var vm = Vm(cli, mapServer: server, previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal("http://127.0.0.1:8/flightmap.html", vm.PreviewUrl);
        Assert.Equal("flightmap.html", vm.PreviewPath);
        Assert.Equal(["flightmap.html"], server.Requests);
        Assert.True(vm.ShowPreview);
        Assert.False(vm.ShowDoneCard);
        Assert.False(vm.PreviewUnavailable);
    }

    [Fact]
    public async Task No_webview_engine_degrades_to_the_done_card_with_a_note()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var server = new FakeMapServer("http://127.0.0.1:8/flightmap.html");
        var vm = Vm(cli, mapServer: server, previewAvailable: static () => false);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Null(vm.PreviewUrl);
        Assert.True(vm.PreviewUnavailable);
        Assert.True(vm.ShowDoneCard);
        Assert.False(vm.ShowPreview);
        Assert.Empty(server.Requests);   // never even asked for a server
    }

    [Fact]
    public async Task Server_failure_degrades_the_same_calm_way()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli, mapServer: new FakeMapServer(null),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);   // a dead preview never fails the run
        Assert.Null(vm.PreviewUrl);
        Assert.True(vm.PreviewUnavailable);
    }

    [Fact]
    public async Task Non_map_done_shows_the_plain_card_without_any_note()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["doctor"] = (DoctorStream, 0),
        });
        var server = new FakeMapServer("http://127.0.0.1:8/x.html");
        var vm = Vm(cli, mapServer: server, previewAvailable: static () => true);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Null(vm.PreviewUrl);
        Assert.False(vm.PreviewUnavailable);
        Assert.True(vm.ShowDoneCard);
        Assert.Empty(server.Requests);
    }

    [Fact]
    public async Task Process_another_clears_the_preview()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli, mapServer: new FakeMapServer("http://127.0.0.1:8/f.html"),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.NotNull(vm.PreviewUrl);
        vm.GoHomeCommand.Execute(null);
        Assert.Equal(FlowStep.Pick, vm.Step);
        Assert.Null(vm.PreviewUrl);
        Assert.Null(vm.PreviewPath);
        Assert.False(vm.ShowPreview);
    }

    [Fact]
    public async Task A_new_run_resets_stale_preview_state()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
            ["doctor"] = (DoctorStream, 0),
        });
        var vm = Vm(cli, mapServer: new FakeMapServer("http://127.0.0.1:8/f.html"),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.NotNull(vm.PreviewUrl);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Null(vm.PreviewUrl);         // the doctor run wiped the old map
        Assert.False(vm.PreviewUnavailable);
    }

    [Fact]
    public async Task Preview_visibility_properties_notify_bindings()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli, mapServer: new FakeMapServer("http://127.0.0.1:8/f.html"),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Contains(nameof(WorkspaceViewModel.ShowPreview), notified);
        Assert.Contains(nameof(WorkspaceViewModel.ShowDoneCard), notified);
    }

    [Fact]
    public async Task Photomap_done_primes_the_preview_too()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["photomap"] = (PhotomapStream, 0),
        });
        var server = new FakeMapServer("http://127.0.0.1:8/photomap.html");
        var vm = Vm(cli, mapServer: server, previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(photos: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal("http://127.0.0.1:8/photomap.html", vm.PreviewUrl);
        Assert.Equal(["photomap.html"], server.Requests);
    }

    [Fact]
    public async Task Failed_map_run_never_asks_for_a_server()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (new[]
            {
                """{"v": 1, "event": "start", "command": "flightmap", "total": 1}""",
                """{"v": 1, "event": "error", "message": "boom"}""",
            }, 1),
        });
        var server = new FakeMapServer("http://127.0.0.1:8/f.html");
        var vm = Vm(cli, mapServer: server, previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Failed, vm.Step);
        Assert.Empty(server.Requests);
        Assert.False(vm.PreviewUnavailable);
    }

    [Fact]
    public async Task Server_exception_degrades_without_failing_the_run()
    {
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli, mapServer: new ThrowingMapServer(),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Null(vm.PreviewUrl);
        Assert.True(vm.PreviewUnavailable);
    }

    [Fact]
    public async Task Canceled_preview_priming_is_cancellation_not_degradation()
    {
        // PrimePreviewAsync must rethrow OperationCanceledException BEFORE
        // its catch-all: cancel during server startup is the Cancel button,
        // not a broken preview — no note, and back to the idle pane.
        var cli = FakeCli.WritePerCommand(_dir, new Dictionary<string, (string[], int)>
        {
            ["flightmap"] = (FlightmapStream, 0),
        });
        var vm = Vm(cli, mapServer: new CanceledMapServer(),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Pick, vm.Step);
        Assert.False(vm.PreviewUnavailable);
        Assert.Null(vm.PreviewUrl);
    }

    [Fact]
    public void Show_in_folder_without_a_preview_is_a_safe_no_op()
    {
        var vm = Vm("unused");
        vm.ShowInFolderCommand.Execute(null);   // must not throw or spawn
        Assert.Null(vm.PreviewPath);
    }

    // M3a: the CLI transparency strip reads CommandPreview — the exact
    // human-facing dji-embed command the current mode + folder would run.
    [Fact]
    public void Command_preview_shows_the_teaching_form_before_a_folder_is_picked()
    {
        var vm = Vm("unused");   // starts on Flight map, no folder
        Assert.Equal("dji-embed flightmap <folder> -r", vm.CommandPreview);
        Assert.DoesNotContain("--progress", vm.CommandPreview);
    }

    [Fact]
    public async Task Command_preview_uses_the_real_folder_once_picked()
    {
        var vm = Vm("unused");
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);
        Assert.Contains(folder, vm.CommandPreview);
        Assert.DoesNotContain("<folder>", vm.CommandPreview);
    }

    [Fact]
    public void Command_preview_tracks_the_selected_mode()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Setup);
        Assert.Equal("dji-embed doctor", vm.CommandPreview);
    }

    [Fact]
    public async Task Command_preview_notifies_on_mode_and_folder_change()
    {
        var vm = Vm("unused");
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
        notified.Clear();
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
    }

    // M3b: Flight map options flow through the run and the live strip.
    [Fact]
    public async Task Flight_map_options_reach_the_flightmap_argv()
    {
        var argsFile = Path.Combine(_dir, "args-opt.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile, FlightmapStream);
        var vm = Vm(cli);
        vm.FlightOptions.SelectedPrivacy =
            vm.FlightOptions.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);
        vm.FlightOptions.ExportAll = true;
        await vm.SetFolderAsync(MakeFolder(srt: true));
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        var argv = File.ReadAllText(argsFile);
        Assert.Contains("--redact fuzz", argv);
        Assert.Contains("--format all", argv);
    }

    [Fact]
    public void Command_preview_reflects_flight_options()
    {
        var vm = Vm("unused");   // default mode Flight map, no folder
        vm.FlightOptions.ExportAll = true;
        Assert.Contains("--format all", vm.CommandPreview);
        vm.FlightOptions.Recursive = false;
        Assert.DoesNotContain(" -r", vm.CommandPreview);
    }

    [Fact]
    public void Changing_a_flight_option_notifies_command_preview()
    {
        var vm = Vm("unused");
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.FlightOptions.JoinGap = 0;
        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
    }

    [Fact]
    public void Only_flight_map_mode_reports_the_options_panel_visible()
    {
        var vm = Vm("unused");
        Assert.True(vm.IsFlightMapMode);
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Assert.False(vm.IsFlightMapMode);
        Assert.Contains(nameof(WorkspaceViewModel.IsFlightMapMode), notified);
    }

    private const string FakeUrl = "http://127.0.0.1:65535/flightmap.html";

    private static WorkspaceViewModel PreviewingVm() =>
        Vm("cli", mapServer: new FakeMapServer(FakeUrl),
            previewAvailable: static () => true);

    [Fact]
    public async Task Picking_a_folder_lists_the_maps_it_already_has()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(
            MakeFolder(srt: true, flightMap: true, photoMap: true));

        Assert.Equal(["Flight map", "Photo map"],
            vm.ExistingMaps.Select(m => m.Title).ToArray());
    }

    [Fact]
    public async Task A_folder_without_maps_lists_none()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true));

        Assert.Empty(vm.ExistingMaps);
    }

    [Fact]
    public async Task A_second_pick_replaces_the_list()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        await vm.SetFolderAsync(MakeFolder(srt: true));

        Assert.Empty(vm.ExistingMaps);
    }

    [Fact]
    public async Task Clearing_the_folder_clears_the_list()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        vm.ClearSourceCommand.Execute(null);

        Assert.Empty(vm.ExistingMaps);
    }

    [Fact]
    public async Task A_folder_pick_drops_the_previous_runs_outputs_and_warnings()
    {
        var vm = Vm("unused");
        vm.Outputs.Add("C:\\old\\flightmap.html");
        vm.Warnings.Add("something from the last folder");

        await vm.SetFolderAsync(MakeFolder(srt: true));

        Assert.Empty(vm.Outputs);
        Assert.Empty(vm.Warnings);
    }

    [Fact]
    public void Process_another_drops_the_previous_runs_outputs_and_warnings()
    {
        // GoHome is the other door into Step == Pick, where a browsed map can
        // now render: the last run's warnings must not frame it.
        var vm = Vm("unused");
        vm.Outputs.Add("C:\\out\\flightmap.html");
        vm.Warnings.Add("something from the run just finished");
        vm.Step = FlowStep.Done;

        vm.GoHomeCommand.Execute(null);

        Assert.Empty(vm.Outputs);
        Assert.Empty(vm.Warnings);
        Assert.True(vm.ShowIdle);
    }

    [Fact]
    public async Task Clearing_the_folder_drops_a_browsed_preview()
    {
        var vm = PreviewingVm();
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        await vm.OpenExistingMapCommand.ExecuteAsync(vm.ExistingMaps[0]);
        Assert.True(vm.ShowPreview);

        vm.ClearSourceCommand.Execute(null);

        Assert.Null(vm.PreviewUrl);
        Assert.False(vm.ShowPreview);
        Assert.True(vm.ShowIdle);
    }

    [Fact]
    public async Task Opening_an_existing_map_previews_it_on_the_pick_step()
    {
        var vm = PreviewingVm();
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        var map = Assert.Single(vm.ExistingMaps);

        await vm.OpenExistingMapCommand.ExecuteAsync(map);

        Assert.Equal(FlowStep.Pick, vm.Step);
        Assert.Equal(FakeUrl, vm.PreviewUrl);
        Assert.Equal(map.Path, vm.PreviewPath);
        Assert.True(vm.ShowPreview);
        Assert.False(vm.ShowIdle);
        Assert.False(vm.ShowDoneCard);
    }

    // The fallback half of OpenExistingMapAsync's contract: no usable inline
    // preview means the user's ask is answered by the browser — still through
    // the map server, so the 360° pano viewer works — and never by preview
    // state a webview-less pane could not render.
    [Fact]
    public async Task Existing_map_open_without_preview_goes_to_the_browser()
    {
        var server = new FakeMapServer(FakeUrl);
        var vm = Vm("cli", mapServer: server,
            previewAvailable: static () => false);
        var launched = new List<string>();
        vm.UrlLauncher = launched.Add;
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        var map = Assert.Single(vm.ExistingMaps);

        await vm.OpenExistingMapCommand.ExecuteAsync(map);

        Assert.Equal([FakeUrl], launched);          // the browser answered the ask
        Assert.Equal([map.Path], server.Requests);  // via the server, not file://
        Assert.Null(vm.PreviewUrl);                 // and no preview state at all
        Assert.Null(vm.PreviewPath);
        Assert.False(vm.ShowPreview);
        Assert.False(vm.PreviewUnavailable);        // a browsed map is not a degradation
        Assert.True(vm.ShowIdle);
    }

    [Fact]
    public async Task Picking_another_folder_drops_a_browsed_preview()
    {
        var vm = PreviewingVm();
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        await vm.OpenExistingMapCommand.ExecuteAsync(vm.ExistingMaps[0]);

        await vm.SetFolderAsync(MakeFolder(srt: true));

        Assert.Null(vm.PreviewUrl);
        Assert.False(vm.ShowPreview);
        Assert.True(vm.ShowIdle);
    }

    [Fact]
    public async Task A_run_takes_the_pane_back_from_a_browsed_map()
    {
        // The run's own output must replace what the user was browsing.
        // FlightmapStream reports the bare name "flightmap.html", which the
        // browsed absolute path can never be mistaken for.
        var argsFile = Path.Combine(_dir, "args-browsed.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile, FlightmapStream);
        var vm = Vm(cli, mapServer: new FakeMapServer(FakeUrl),
            previewAvailable: static () => true);
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        await vm.OpenExistingMapCommand.ExecuteAsync(vm.ExistingMaps[0]);
        Assert.True(vm.ShowPreview);
        Assert.True(Path.IsPathRooted(vm.PreviewPath));

        await vm.RunCommand.ExecuteAsync(null);

        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal("flightmap.html", vm.PreviewPath);
    }

    [Fact]
    public async Task The_open_command_is_disabled_while_a_run_is_in_flight()
    {
        var gate = new TaskCompletionSource();
        Func<string, FolderContents> inspect =
            _ => Contents(logs: true, topLogs: true);
        var cli = FakeCli.WriteEventStream(_dir, FlightmapStream);
        var vm = Vm(cli, mapServer: new FakeMapServer(FakeUrl),
            previewAvailable: static () => true,
            folderInspector: dir => inspect(dir));
        await vm.SetFolderAsync(MakeFolder(srt: true, flightMap: true));
        var map = vm.ExistingMaps[0];
        Assert.True(vm.OpenExistingMapCommand.CanExecute(map));
        // CanExecute is evaluated live, so the assertion below passes with or
        // without the notification — but a real button only re-reads it when
        // told to, so assert the telling too.
        var notified = false;
        vm.OpenExistingMapCommand.CanExecuteChanged += (_, _) => notified = true;
        inspect = _ =>
        {
            gate.Task.Wait();
            return Contents(logs: true, topLogs: true);
        };

        var run = vm.RunCommand.ExecuteAsync(null);

        Assert.False(vm.OpenExistingMapCommand.CanExecute(map));
        Assert.True(notified);
        gate.SetResult();
        await run;
    }

    [Fact]
    public void The_idle_hero_shows_when_nothing_is_previewed()
    {
        var vm = Vm("unused");

        Assert.True(vm.ShowIdle);
        Assert.False(vm.ShowPreview);
    }

    // M3c: Photo map options flow through the run and the live strip.
    [Fact]
    public async Task Photo_map_options_reach_the_photomap_argv()
    {
        var argsFile = Path.Combine(_dir, "args-photo-opt.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile, PhotomapStream);
        var vm = Vm(cli);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        vm.PhotoOptions.SelectedPrivacy =
            vm.PhotoOptions.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);
        vm.PhotoOptions.ShowCamera = false;
        await vm.SetFolderAsync(MakeFolder(photos: true));
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        await vm.RunCommand.ExecuteAsync(null);
        Assert.Equal(FlowStep.Done, vm.Step);
        var argv = File.ReadAllText(argsFile);
        Assert.Contains("--redact fuzz", argv);
        Assert.Contains("--popup-fields name,timestamp,altitude,credit", argv);
        Assert.Contains("--link-originals", argv);
    }

    [Fact]
    public void Command_preview_reflects_photo_options()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Assert.Contains("photomap", vm.CommandPreview);
        vm.PhotoOptions.ExportAll = true;
        Assert.Contains("--format all", vm.CommandPreview);
        vm.PhotoOptions.LinkOriginals = false;
        Assert.DoesNotContain("--link-originals", vm.CommandPreview);
    }

    [Fact]
    public void Changing_a_photo_option_notifies_command_preview()
    {
        var vm = Vm("unused");
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.PhotoOptions.ShowCredit = false;
        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
    }

    [Fact]
    public void Only_photo_map_mode_reports_the_photo_options_panel_visible()
    {
        var vm = Vm("unused");   // default mode Flight map
        Assert.False(vm.IsPhotoMapMode);
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.PhotoMap);
        Assert.True(vm.IsPhotoMapMode);
        Assert.False(vm.IsFlightMapMode);
        Assert.Contains(nameof(WorkspaceViewModel.IsPhotoMapMode), notified);
    }

    // M3d: Embed options flow through the run and the live strip.
    [Fact]
    public async Task Embed_options_reach_the_embed_argv()
    {
        var argsFile = Path.Combine(_dir, "args-embed-opt.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": ["/footage/processed"], "summary": {}}""",
        ]);
        var vm = Vm(cli);
        vm.EmbedOptions.SelectedPrivacy = vm.EmbedOptions.PrivacyOptions
            .Single(p => p.Value == TelemetryPrivacy.Drop);
        vm.EmbedOptions.SelectedContainer =
            vm.EmbedOptions.Containers.Single(c => c.Key == "mkv");
        vm.EmbedOptions.DatAuto = true;
        await vm.SetFolderAsync(MakeFolder(videos: true));
        Assert.Equal(WorkspaceModeKind.Embed, vm.SelectedMode.Kind);

        await vm.RunCommand.ExecuteAsync(null);

        Assert.Equal(FlowStep.Done, vm.Step);
        var argv = File.ReadAllText(argsFile);
        Assert.Contains("--redact drop", argv);
        Assert.Contains("--container mkv", argv);
        Assert.Contains("--dat-auto", argv);
        Assert.DoesNotContain("--overwrite", argv);
    }

    [Fact]
    public void Command_preview_reflects_embed_options()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Assert.Equal("dji-embed embed <folder>", vm.CommandPreview);
        vm.EmbedOptions.ExtractHome = true;
        Assert.Contains("--extract-home", vm.CommandPreview);
        vm.EmbedOptions.UseExifTool = true;
        Assert.Contains("--exiftool", vm.CommandPreview);
    }

    [Fact]
    public void Changing_an_embed_option_notifies_command_preview()
    {
        var vm = Vm("unused");
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.EmbedOptions.AudioSidecar = true;
        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
    }

    [Fact]
    public void Only_embed_mode_reports_the_embed_options_panel_visible()
    {
        var vm = Vm("unused");   // default mode Flight map
        Assert.False(vm.IsEmbedMode);
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Embed);
        Assert.True(vm.IsEmbedMode);
        Assert.False(vm.IsFlightMapMode);
        Assert.False(vm.IsPhotoMapMode);
        Assert.Contains(nameof(WorkspaceViewModel.IsEmbedMode), notified);
    }

    [Fact]
    public void Changing_a_convert_option_notifies_command_preview()
    {
        var vm = Vm("unused");
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.ConvertOptions.TzOffset = "2";
        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
    }

    [Fact]
    public void Only_convert_mode_reports_the_convert_options_panel_visible()
    {
        var vm = Vm("unused");   // default mode Flight map
        Assert.False(vm.IsConvertMode);
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);
        vm.SelectedMode = WorkspaceMode.Of(WorkspaceModeKind.Convert);
        Assert.True(vm.IsConvertMode);
        Assert.False(vm.IsFlightMapMode);
        Assert.False(vm.IsPhotoMapMode);
        Assert.False(vm.IsEmbedMode);
        Assert.Contains(nameof(WorkspaceViewModel.IsConvertMode), notified);
    }

    // #334: the CLI transparency strip's whole promise is that the command it
    // shows IS the command the runner executes — the runner may append only
    // the machine-only `--progress jsonl`. Argv-fragment tests and preview
    // tests each cover one side; these pin the two sides to each other, one
    // per mode, argv-to-argv (via SplitPreview) so CommandLine.Format's
    // display quoting stays free to change.
    private static void AssertStripEqualsExecutedArgv(
        string preview, string argsFile)
    {
        var executed = File.ReadAllLines(argsFile);
        Assert.Equal(["--progress", "jsonl"], executed[^2..]);
        var shown = SplitPreview(preview);
        Assert.Equal("dji-embed", shown[0]);
        Assert.Equal(shown.Skip(1), executed[..^2]);
    }

    /// <summary>Splits the strip's display string back into an argv,
    /// honouring the double quotes CommandLine.Format adds around arguments
    /// with spaces. Deliberately test-side: the promise under test is about
    /// the rendered string, whatever quoting produced it.</summary>
    private static List<string> SplitPreview(string preview)
    {
        var tokens = new List<string>();
        var current = new System.Text.StringBuilder();
        var inQuotes = false;
        var hasToken = false;   // distinguishes "" (an empty argument) from nothing
        foreach (var c in preview)
        {
            if (c == '"')
            {
                inQuotes = !inQuotes;
                hasToken = true;
            }
            else if (char.IsWhiteSpace(c) && !inQuotes)
            {
                if (hasToken)
                {
                    tokens.Add(current.ToString());
                    current.Clear();
                    hasToken = false;
                }
            }
            else
            {
                current.Append(c);
                hasToken = true;
            }
        }
        if (hasToken)
        {
            tokens.Add(current.ToString());
        }
        return tokens;
    }

    [Fact]
    public async Task Flight_map_strip_equals_the_executed_argv()
    {
        var argsFile = Path.Combine(_dir, "argv-strip-fm.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile, FlightmapStream);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.FlightOptions.SelectedTileStyle =
            vm.FlightOptions.TileStyles.Single(t => t.Key == "opentopomap");
        vm.FlightOptions.SelectedPrivacy =
            vm.FlightOptions.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);
        vm.FlightOptions.JoinGap = 0;
        vm.FlightOptions.Title = "My Alps Trip";   // quoted in the strip
        var preview = vm.CommandPreview;

        await vm.RunCommand.ExecuteAsync(null);

        Assert.Equal(FlowStep.Done, vm.Step);
        AssertStripEqualsExecutedArgv(preview, argsFile);
    }

    [Fact]
    public async Task Photo_map_strip_equals_the_executed_argv()
    {
        var argsFile = Path.Combine(_dir, "argv-strip-pm.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile, PhotomapStream);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.Equal(WorkspaceModeKind.PhotoMap, vm.SelectedMode.Kind);
        vm.PhotoOptions.SelectedTileStyle =
            vm.PhotoOptions.TileStyles.Single(t => t.Key == "cyclosm");
        vm.PhotoOptions.ShowName = false;    // forces a --popup-fields subset
        vm.PhotoOptions.ShowCredit = false;
        vm.PhotoOptions.ExportAll = true;
        var preview = vm.CommandPreview;

        await vm.RunCommand.ExecuteAsync(null);

        Assert.Equal(FlowStep.Done, vm.Step);
        AssertStripEqualsExecutedArgv(preview, argsFile);
    }

    [Fact]
    public async Task Embed_strip_equals_the_executed_argv()
    {
        var argsFile = Path.Combine(_dir, "argv-strip-em.txt");
        var cli = FakeCli.WriteArgvLinesRecorder(_dir, argsFile,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": ["/footage/processed"], "summary": {}}""",
        ]);
        var vm = Vm(cli);
        await vm.SetFolderAsync(MakeFolder(videos: true));
        Assert.Equal(WorkspaceModeKind.Embed, vm.SelectedMode.Kind);
        vm.EmbedOptions.SelectedPrivacy = vm.EmbedOptions.PrivacyOptions
            .Single(p => p.Value == TelemetryPrivacy.Fuzz);
        vm.EmbedOptions.SelectedContainer =
            vm.EmbedOptions.Containers.Single(c => c.Key == "mkv");
        vm.EmbedOptions.ExtractHome = true;
        vm.EmbedOptions.AudioSidecar = true;
        var preview = vm.CommandPreview;

        await vm.RunCommand.ExecuteAsync(null);

        Assert.Equal(FlowStep.Done, vm.Step);
        AssertStripEqualsExecutedArgv(preview, argsFile);
    }

    [Fact]
    public async Task A_new_folder_clears_the_embed_output_but_keeps_other_options()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(videos: true));
        vm.EmbedOptions.Output = Path.Combine(_dir, "copies");
        vm.EmbedOptions.SelectedContainer =
            vm.EmbedOptions.Containers.Single(c => c.Key == "mkv");
        vm.EmbedOptions.ExtractHome = true;

        await vm.SetFolderAsync(MakeFolder(videos: true));

        Assert.Equal("", vm.EmbedOptions.Output);
        Assert.Equal("mkv", vm.EmbedOptions.SelectedContainer.Key);
        Assert.True(vm.EmbedOptions.ExtractHome);
    }

    // Branch review finding: photomap writes each pin's href RELATIVE to the
    // HTML file, so a "Save map to" redirected outside the source folder
    // silently breaks every "open the original" link — and with it the 360°
    // panorama viewer. PhotoLinksCannotReachOriginals is the truth behind the
    // panel's warning note.
    [Fact]
    public async Task Link_reach_note_is_false_at_defaults()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.False(vm.PhotoLinksCannotReachOriginals);
    }

    [Fact]
    public async Task Link_reach_note_is_false_when_output_sits_in_the_source_folder()
    {
        var vm = Vm("unused");
        var folder = MakeFolder(photos: true);
        await vm.SetFolderAsync(folder);
        vm.PhotoOptions.Output = Path.Combine(folder, "photomap.html");
        Assert.False(vm.PhotoLinksCannotReachOriginals);
    }

    [Fact]
    public async Task Link_reach_note_is_true_when_output_sits_outside_the_source_folder()
    {
        var vm = Vm("unused");
        var folder = MakeFolder(photos: true);
        await vm.SetFolderAsync(folder);
        vm.PhotoOptions.Output = Path.Combine(_dir, "photomap.html");
        Assert.True(vm.PhotoLinksCannotReachOriginals);
    }

    [Fact]
    public async Task Link_reach_note_is_false_when_link_originals_is_off()
    {
        var vm = Vm("unused");
        var folder = MakeFolder(photos: true);
        await vm.SetFolderAsync(folder);
        vm.PhotoOptions.Output = Path.Combine(_dir, "photomap.html");
        vm.PhotoOptions.LinkOriginals = false;
        Assert.False(vm.PhotoLinksCannotReachOriginals);
    }

    // D:\Trip and D:\Trip\ must read as the same folder — SelectedFolder is
    // whatever the drop/pick handed us, untrimmed.
    [Fact]
    public async Task Link_reach_note_treats_a_trailing_separator_as_the_same_folder()
    {
        var vm = Vm("unused");
        var folder = MakeFolder(photos: true);
        await vm.SetFolderAsync(folder + Path.DirectorySeparatorChar);
        vm.PhotoOptions.Output = Path.Combine(folder, "photomap.html");
        Assert.False(vm.PhotoLinksCannotReachOriginals);
    }

    [Fact]
    public async Task Link_reach_note_notifies_on_output_and_folder_changes()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(photos: true));
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);

        vm.PhotoOptions.Output = Path.Combine(_dir, "photomap.html");
        Assert.Contains(nameof(WorkspaceViewModel.PhotoLinksCannotReachOriginals), notified);

        notified.Clear();
        await vm.SetFolderAsync(MakeFolder(photos: true));
        Assert.Contains(nameof(WorkspaceViewModel.PhotoLinksCannotReachOriginals), notified);
    }

    [Fact]
    public async Task Link_reach_note_is_false_for_a_garbage_output_path()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(photos: true));
        vm.PhotoOptions.Output = " bad";
        Assert.False(vm.PhotoLinksCannotReachOriginals);
    }

    // Branch review finding (present since M3b, doubled by M3c): an absolute
    // "Save map to" override belongs to the folder it was chosen for — carry
    // it to a new folder and that folder's map silently overwrites the old
    // one, or lands nowhere the new folder shows. Every OTHER option is
    // deliberately app-session state (the GUI 2.0 spec: "options survive
    // while the app is open") — this test guards both halves so neither
    // regresses into the other.
    [Fact]
    public async Task A_new_folder_clears_the_save_map_override_but_keeps_other_options()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.FlightOptions.Output = Path.Combine(_dir, "flightmap.html");
        vm.FlightOptions.SelectedPrivacy =
            vm.FlightOptions.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);
        vm.PhotoOptions.Output = Path.Combine(_dir, "photomap.html");
        vm.PhotoOptions.SelectedTileStyle =
            vm.PhotoOptions.TileStyles.Single(t => t.Key == "opentopomap");
        vm.PhotoOptions.ShowCamera = false;

        await vm.SetFolderAsync(MakeFolder(srt: true));

        Assert.Equal("", vm.FlightOptions.Output);
        Assert.Equal("", vm.PhotoOptions.Output);
        Assert.Equal(MapPrivacy.Fuzz, vm.FlightOptions.SelectedPrivacy.Value);
        Assert.Equal("opentopomap", vm.PhotoOptions.SelectedTileStyle.Key);
        Assert.False(vm.PhotoOptions.ShowCamera);
    }

    // The ✕ next to the folder path removes the folder, so an absolute output
    // override chosen for it no longer has an owner — without this the idle
    // strip advertises a path from a folder that is no longer selected.
    [Fact]
    public async Task Clearing_the_folder_clears_every_save_override()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.FlightOptions.Output = Path.Combine(_dir, "flightmap.html");
        vm.PhotoOptions.Output = Path.Combine(_dir, "photomap.html");
        vm.EmbedOptions.Output = Path.Combine(_dir, "copies");

        vm.ClearSourceCommand.Execute(null);

        Assert.Equal("", vm.FlightOptions.Output);
        Assert.Equal("", vm.PhotoOptions.Output);
        Assert.Equal("", vm.EmbedOptions.Output);
    }

    // The reset is only half the fix: the strip has to be told to recompute,
    // or the cleared path stays on screen as text.
    [Fact]
    public async Task Clearing_the_folder_refreshes_the_command_strip()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.FlightOptions.Output = Path.Combine(_dir, "flightmap.html");
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);

        vm.ClearSourceCommand.Execute(null);

        Assert.Contains(nameof(WorkspaceViewModel.CommandPreview), notified);
        Assert.Equal("dji-embed flightmap <folder> -r", vm.CommandPreview);
    }

    // Review finding: ✕ after a finished run nulled the preview but left
    // Step == Done, so ShowDoneCard stayed true — the run's outputs and
    // warnings listed with no folder selected and no drop hero behind them.
    // That is the same failure the ResetPreview comment cites; the reset just
    // stopped one property short. Synthetic Done, as in the GoHome sibling
    // above: the bug is in the reset, not in how Done was reached.
    [Fact]
    public async Task Clearing_the_folder_after_a_run_returns_to_the_hero()
    {
        var vm = Vm("unused");
        await vm.SetFolderAsync(MakeFolder(srt: true));
        vm.Outputs.Add("C:\\out\\flightmap.html");
        vm.Warnings.Add("something from the run just finished");
        vm.Step = FlowStep.Done;

        vm.ClearSourceCommand.Execute(null);

        Assert.True(vm.ShowIdle);
        Assert.False(vm.ShowDoneCard);
        Assert.Empty(vm.Outputs);
        Assert.Empty(vm.Warnings);
    }

    // SetFolderAsync is inert mid-run; ✕ was not, so it could yank the folder
    // out from under a running job — and once it also cleared the three
    // output overrides, a mid-run ✕ silently discarded those too.
    [Fact]
    public async Task Clearing_the_folder_is_inert_while_a_run_is_in_flight()
    {
        var cli = FakeCli.WriteEventStream(_dir, FlightmapStream);
        Func<string, FolderContents> inspect =
            _ => Contents(logs: true, topLogs: true);
        var vm = Vm(cli, folderInspector: dir => inspect(dir));
        var folder = MakeFolder(srt: true);
        await vm.SetFolderAsync(folder);
        vm.FlightOptions.Output = Path.Combine(_dir, "flightmap.html");
        vm.EmbedOptions.Output = Path.Combine(_dir, "copies");
        var gate = new TaskCompletionSource();
        inspect = _ =>
        {
            gate.Task.Wait();
            return Contents(logs: true, topLogs: true);
        };
        var run = vm.RunCommand.ExecuteAsync(null);

        vm.ClearSourceCommand.Execute(null);

        Assert.Equal(folder, vm.SelectedFolder);
        Assert.Equal(Path.Combine(_dir, "flightmap.html"), vm.FlightOptions.Output);
        Assert.Equal(Path.Combine(_dir, "copies"), vm.EmbedOptions.Output);
        gate.SetResult();
        await run;
    }

    private sealed class ThrowingMapServer : IMapServer
    {
        public Task<string?> GetUrlAsync(
            string cliPath, string htmlPath, CancellationToken cancellationToken) =>
            throw new InvalidOperationException("server exploded");
    }

    private sealed class CanceledMapServer : IMapServer
    {
        public Task<string?> GetUrlAsync(
            string cliPath, string htmlPath, CancellationToken cancellationToken) =>
            throw new OperationCanceledException();
    }
}
