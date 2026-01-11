
/**
 * Processes text to inject citations based on Grounding Metadata.
 * Primarily used for Google Search Grounding results.
 */
export function addCitations(text: string, groundingMetadata: any): string {
    if (!groundingMetadata || !groundingMetadata.groundingSupports || !groundingMetadata.groundingChunks) {
        return text;
    }
    const supports = groundingMetadata.groundingSupports;
    const chunks = groundingMetadata.groundingChunks;
    
    // Sort supports by descending index to avoid offset issues when inserting
    const sortedSupports = [...supports].sort(
        (a: any, b: any) => (b.segment?.endIndex ?? 0) - (a.segment?.endIndex ?? 0),
    );

    let newText = text;
    for (const support of sortedSupports) {
        const endIndex = support.segment?.endIndex;
        if (endIndex === undefined || !support.groundingChunkIndices?.length) {
            continue;
        }
        
        // Build [1][2] style links
        const citationLinks = support.groundingChunkIndices
        .map((i: number) => {
            const uri = chunks[i]?.web?.uri;
            if (uri) return ` [${i + 1}](${uri})`;
            return null;
        })
        .filter(Boolean);

        if (citationLinks.length > 0 && endIndex <= newText.length) {
            newText = newText.slice(0, endIndex) + citationLinks.join("") + newText.slice(endIndex);
        }
    }
    return newText;
}
