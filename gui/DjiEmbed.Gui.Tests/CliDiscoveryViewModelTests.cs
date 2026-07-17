using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class CliDiscoveryViewModelTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-clidisc-").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    [Fact]
    public void Starter_commands_all_run_dji_embed()
    {
        var vm = new CliDiscoveryViewModel(null, () => { });
        Assert.NotEmpty(vm.StarterCommands);
        Assert.All(vm.StarterCommands, c =>
        {
            Assert.StartsWith("dji-embed", c.Command);
            Assert.False(string.IsNullOrWhiteSpace(c.Description));
        });
    }

    [Fact]
    public async Task Load_help_captures_the_cli_help_output()
    {
        var cli = FakeCli.WriteEventStream(_dir,
            ["Usage: dji-embed [OPTIONS] COMMAND", "  photomap  Map photos"]);
        var vm = new CliDiscoveryViewModel(cli, () => { });

        await vm.LoadHelpCommand.ExecuteAsync(null);

        Assert.Contains("Usage: dji-embed", vm.HelpText);
        Assert.Contains("photomap", vm.HelpText);
    }

    [Fact]
    public async Task Expanding_triggers_the_help_load()
    {
        var cli = FakeCli.WriteEventStream(_dir, ["Usage: dji-embed"]);
        var vm = new CliDiscoveryViewModel(cli, () => { });

        vm.HelpExpanded = true;

        // The expander load is fire-and-forget; wait for it to land.
        var deadline = DateTime.UtcNow.AddSeconds(10);
        while (vm.HelpText is null && DateTime.UtcNow < deadline)
        {
            await Task.Delay(50, TestContext.Current.CancellationToken);
        }
        Assert.Contains("Usage: dji-embed", vm.HelpText);
    }

    [Fact]
    public async Task Help_is_loaded_only_once()
    {
        var argsFile = Path.Combine(_dir, "args.txt");
        var cli = FakeCli.WriteArgsRecorder(_dir, argsFile, ["Usage: x"]);
        var vm = new CliDiscoveryViewModel(cli, () => { });

        await vm.LoadHelpCommand.ExecuteAsync(null);
        await vm.LoadHelpCommand.ExecuteAsync(null);

        Assert.Single(File.ReadAllLines(argsFile));
    }

    [Fact]
    public async Task Missing_cli_shows_the_reinstall_message()
    {
        var vm = new CliDiscoveryViewModel(null, () => { });
        await vm.LoadHelpCommand.ExecuteAsync(null);
        Assert.Contains("could not be found", vm.HelpText);
    }

    [Fact]
    public async Task Broken_cli_shows_the_manual_fallback()
    {
        var cli = FakeCli.WriteEventStream(_dir, ["boom"], exitCode: 2);
        var vm = new CliDiscoveryViewModel(cli, () => { });
        await vm.LoadHelpCommand.ExecuteAsync(null);
        Assert.Contains("dji-embed --help", vm.HelpText);
    }
}
