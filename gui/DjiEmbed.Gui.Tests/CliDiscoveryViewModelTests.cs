using System.Runtime.InteropServices;
using DjiEmbed.Gui.Services;
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
    public void Windows_intro_keeps_the_installer_path_claim()
    {
        // On Windows the sentence is true: the installer appends the CLI
        // to PATH, so bare dji-embed works in any terminal.
        var text = CliDiscoveryViewModel.IntroTextFor(OSPlatform.Windows);
        Assert.Contains("put it on your PATH", text);
        Assert.Contains("type dji-embed", text);
    }

    [Fact]
    public void Macos_intro_never_claims_path_or_bare_typing()
    {
        // #442: the DMG install puts the CLI inside the app bundle and
        // touches no PATH — telling a Mac user to "type dji-embed" lands
        // on command-not-found.
        var text = CliDiscoveryViewModel.IntroTextFor(OSPlatform.OSX);
        Assert.DoesNotContain("PATH", text);
        Assert.DoesNotContain("type dji-embed", text);
        Assert.Contains("inside this app", text);
    }

    [Fact]
    public void Linux_intro_points_at_pipx()
    {
        // No installer exists on Linux (#360); pipx is the documented
        // route to a CLI that works in any terminal.
        var text = CliDiscoveryViewModel.IntroTextFor(OSPlatform.Linux);
        Assert.DoesNotContain("installer", text);
        Assert.Contains("pipx install dji-drone-metadata-embedder", text);
    }

    [Fact]
    public void Intro_text_property_follows_the_current_platform()
    {
        var vm = new CliDiscoveryViewModel(null, () => { });
        Assert.Equal(
            CliDiscoveryViewModel.IntroTextFor(
                DjiEmbed.Gui.Services.Platforms.Current),
            vm.IntroText);
    }

    [Fact]
    public void Starter_command_sample_folders_match_the_platform()
    {
        // The examples are copy-paste bait — a D:\ drive path handed to a
        // macOS user cannot work, so the sample folder follows the OS.
        var windows = CliDiscoveryViewModel.StarterCommandsFor(
            OSPlatform.Windows);
        Assert.Contains(windows, c => c.Command.Contains(@"D:\Footage"));

        foreach (var platform in new[] { OSPlatform.OSX, OSPlatform.Linux })
        {
            var commands = CliDiscoveryViewModel.StarterCommandsFor(platform);
            Assert.DoesNotContain(commands, c => c.Command.Contains(@"D:\"));
            Assert.Contains(commands, c => c.Command.Contains(
                platform == OSPlatform.OSX
                    ? "~/Movies/Footage" : "~/Videos/Footage"));
        }
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

    [Fact]
    public void A_terminal_that_opened_says_nothing()
    {
        // The Terminal window in front of them is the feedback.
        Assert.Null(CliDiscoveryViewModel.TerminalMessageFor(
            TerminalLaunchResult.Started, OSPlatform.OSX));
    }

    [Fact]
    public void Denied_automation_names_the_pane_that_undoes_it()
    {
        // #443: macOS remembers Don't Allow, so every later click is
        // silent too — the way back out has to be on screen.
        var text = CliDiscoveryViewModel.TerminalMessageFor(
            TerminalLaunchResult.AutomationDenied, OSPlatform.OSX);

        Assert.Contains("System Settings", text);
        Assert.Contains("Privacy & Security", text);
        Assert.Contains("Automation", text);
        Assert.Contains("DJI Metadata Embedder", text);
        Assert.Contains("Terminal", text);
    }

    [Fact]
    public void A_failed_launch_hands_the_job_back_to_the_user()
    {
        foreach (var platform in
                 new[] { OSPlatform.Windows, OSPlatform.OSX, OSPlatform.Linux })
        {
            var text = CliDiscoveryViewModel.TerminalMessageFor(
                TerminalLaunchResult.Failed, platform);
            Assert.False(string.IsNullOrWhiteSpace(text));
        }
    }

    [Fact]
    public void The_macos_fallback_never_tells_them_to_type_bare_dji_embed()
    {
        // #442 again: nothing puts the CLI on PATH on macOS, so the
        // fallback advice cannot be "open Terminal and type dji-embed".
        var text = CliDiscoveryViewModel.TerminalMessageFor(
            TerminalLaunchResult.Failed, OSPlatform.OSX);

        Assert.DoesNotContain("type dji-embed", text);
        Assert.DoesNotContain("run dji-embed", text);
    }

    [Fact]
    public async Task Clicking_the_button_surfaces_a_denied_launch()
    {
        var vm = new CliDiscoveryViewModel(null, () => { },
            _ => Task.FromResult(TerminalLaunchResult.AutomationDenied));

        await vm.OpenTerminalCommand.ExecuteAsync(null);

        Assert.Contains("Automation", vm.TerminalMessage);
    }

    [Fact]
    public async Task A_launch_that_works_clears_an_earlier_complaint()
    {
        var result = TerminalLaunchResult.AutomationDenied;
        var vm = new CliDiscoveryViewModel(null, () => { },
            _ => Task.FromResult(result));

        await vm.OpenTerminalCommand.ExecuteAsync(null);
        Assert.NotNull(vm.TerminalMessage);

        // They granted the permission and clicked again.
        result = TerminalLaunchResult.Started;
        await vm.OpenTerminalCommand.ExecuteAsync(null);

        Assert.Null(vm.TerminalMessage);
    }

    [Fact]
    public async Task The_launch_gets_the_bundled_cli_path()
    {
        string? seen = null;
        var vm = new CliDiscoveryViewModel("/Applications/x.app/dji-embed",
            () => { },
            path =>
            {
                seen = path;
                return Task.FromResult(TerminalLaunchResult.Started);
            });

        await vm.OpenTerminalCommand.ExecuteAsync(null);

        Assert.Equal("/Applications/x.app/dji-embed", seen);
    }
}
