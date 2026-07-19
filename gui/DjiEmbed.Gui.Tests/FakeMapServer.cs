using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

/// <summary>
/// Deterministic stand-in for the managed map server: records every HTML
/// path it is asked about and answers with a fixed URL (null = "the server
/// could not start"), so no test ever spawns a real `serve` child.
/// </summary>
internal sealed class FakeMapServer(string? url) : IMapServer
{
    public List<string> Requests { get; } = [];

    public Task<string?> GetUrlAsync(string cliPath, string htmlPath)
    {
        Requests.Add(htmlPath);
        return Task.FromResult(url);
    }
}
