using System.Threading.Tasks;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// The map-serving seam: hands out a local-HTTP URL for a generated HTML
/// map. Implemented by <see cref="MapServer"/>; faked in tests so no
/// <c>dji-embed serve</c> child is ever spawned there.
/// </summary>
public interface IMapServer
{
    /// <summary>Null when no server could be started — callers fall back
    /// to opening the file directly.</summary>
    Task<string?> GetUrlAsync(string cliPath, string htmlPath);
}
