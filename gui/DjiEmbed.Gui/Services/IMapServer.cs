using System.Threading;
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
    /// to opening the file directly. Cancellation surfaces as
    /// OperationCanceledException, never as null.</summary>
    Task<string?> GetUrlAsync(
        string cliPath, string htmlPath, CancellationToken cancellationToken);

    /// <summary>Launches (or reuses) a <c>dji-embed panoedit</c> child for
    /// <paramref name="folder"/> and returns its editor URL (#440). Null
    /// when the editor could not start (no panoramas, no CLI);
    /// cancellation surfaces as OperationCanceledException.
    /// <paramref name="fullResolution"/> serves panoramas full-size
    /// (<c>--max-width 0</c>, #532); children with different resolution
    /// modes never share a server.</summary>
    Task<string?> GetEditorUrlAsync(
        string cliPath, string folder, bool fullResolution,
        CancellationToken cancellationToken);
}
