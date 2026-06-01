const HEADER_SELECT_MIN_WIDTH_CH = 16;
const HEADER_SELECT_HORIZONTAL_PADDING_CH = 5;

const getTextWidthCh = (value: string) => {
  return Array.from(value).reduce((width, char) => {
    const codePoint = char.codePointAt(0) || 0;
    return width + (codePoint > 0xff ? 2 : 1);
  }, 0);
};

export const getHeaderSelectWidthCh = (
  labels: ReadonlyArray<string | null | undefined>,
  fallbackLabel: string
) => {
  const candidates = [fallbackLabel, ...labels].filter((label): label is string => Boolean(label));
  const longestLabelWidth = Math.max(...candidates.map((label) => getTextWidthCh(label)));

  return Math.max(
    HEADER_SELECT_MIN_WIDTH_CH,
    longestLabelWidth + HEADER_SELECT_HORIZONTAL_PADDING_CH
  );
};
