using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using Avalonia.VisualTree;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;
using Xunit;

namespace DjiEmbed.Gui.Tests;

// #292: long runs should feel alive ("DJI_0042.MP4 (3 of 12)") and CLI
// warnings must reach the Done screen — a silent partial success looks
// like a full success.
public class FlowProgressAndWarningsTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-flowprog-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string MakeFolder()
    {
        var folder = Path.Combine(_dir, "footage");
        Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder, "DJI_0001.MP4"), "");
        File.WriteAllText(Path.Combine(folder, "DJI_0001.SRT"), "");
        return folder;
    }

    private static EmbedTelemetryViewModel Vm(string? cli) =>
        new(cli, new DjiEmbedRunner(), () => { });

    [Fact]
    public void Progress_detail_names_the_file_and_the_count()
    {
        var vm = Vm(null);
        vm.CurrentItem = "DJI_0042.MP4";
        vm.Current = 3;
        vm.Total = 12;
        Assert.Equal("DJI_0042.MP4 (3 of 12)", vm.ProgressDetail);
    }

    [Fact]
    public void Progress_detail_without_a_total_is_just_the_file()
    {
        var vm = Vm(null);
        vm.CurrentItem = "DJI_0042.MP4";
        Assert.Equal("DJI_0042.MP4", vm.ProgressDetail);
    }

    [Fact]
    public void Progress_detail_without_an_item_is_null()
    {
        var vm = Vm(null);
        vm.Current = 3;
        vm.Total = 12;
        Assert.Null(vm.ProgressDetail);
    }

    [Fact]
    public async Task Warning_events_are_collected_for_the_done_screen()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 3}""",
            """{"v": 1, "event": "warning", "message": "no matching SRT", "item": "DJI_0002.MP4"}""",
            """{"v": 1, "event": "warning", "message": "2 files skipped"}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": ["/footage/processed"], "summary": {}}""",
        ]);
        var vm = Vm(cli);
        await vm.StartCommand.ExecuteAsync(MakeFolder());
        Assert.Equal(FlowStep.Done, vm.Step);
        Assert.Equal(
            ["DJI_0002.MP4: no matching SRT", "2 files skipped"],
            vm.Warnings);
    }

    [Fact]
    public async Task Warnings_do_not_leak_into_the_next_run()
    {
        var cli = FakeCli.WriteEventStream(_dir,
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "warning", "message": "one warning"}""",
            """{"v": 1, "event": "result", "ok": true, "outputs": [], "summary": {}}""",
        ]);
        var vm = Vm(cli);
        var folder = MakeFolder();
        await vm.StartCommand.ExecuteAsync(folder);
        await vm.StartCommand.ExecuteAsync(folder);
        Assert.Equal(["one warning"], vm.Warnings);
    }

    [AvaloniaFact]
    public void Running_screen_shows_the_progress_detail()
    {
        var vm = Vm(null);
        vm.Step = FlowStep.Running;
        vm.StatusText = "Embedding your flight data…";
        vm.CurrentItem = "DJI_0042.MP4";
        vm.Current = 3;
        vm.Total = 12;
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });
        Assert.Contains(Texts(window), t => t == "DJI_0042.MP4 (3 of 12)");
    }

    [AvaloniaFact]
    public void Embed_done_screen_shows_warnings()
    {
        var vm = Vm(null);
        vm.Step = FlowStep.Done;
        vm.Warnings.Add("DJI_0002.MP4: no matching SRT");
        var window = ShowView(new EmbedTelemetryView { DataContext = vm });
        Assert.Contains(Texts(window),
            t => t?.Contains("no matching SRT") == true);
    }

    [AvaloniaFact]
    public void Makemap_done_screen_shows_warnings()
    {
        var vm = new MakeMapViewModel(null, new DjiEmbedRunner(), () => { });
        vm.Step = FlowStep.Done;
        vm.Warnings.Add("IMG_0001.JPG: no GPS position");
        var window = ShowView(new MakeMapView { DataContext = vm });
        Assert.Contains(Texts(window),
            t => t?.Contains("no GPS position") == true);
    }

    private static Window ShowView(Control view)
    {
        var window = new Window { Width = 560, Height = 520, Content = view };
        window.Show();
        Dispatcher.UIThread.RunJobs();
        window.UpdateLayout();
        return window;
    }

    private static List<string?> Texts(Window window) =>
        window.GetVisualDescendants().OfType<TextBlock>()
            .Where(t => t.IsEffectivelyVisible)
            .Select(t => t.Text).ToList();
}
