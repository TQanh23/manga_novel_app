import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Pressable, Text } from 'react-native';

import {
  DEFAULT_SETTINGS,
  parseSettings,
  ReaderSettingsProvider,
  useReaderSettings,
} from '@/reader/settings';

beforeEach(async () => {
  await AsyncStorage.clear();
  jest.clearAllMocks();
});

function Probe() {
  const { settings, update } = useReaderSettings();
  return (
    <>
      <Text>{JSON.stringify(settings)}</Text>
      <Pressable accessibilityRole="button" onPress={() => update({ size: 4, theme: 'dark' })}>
        <Text>Change</Text>
      </Pressable>
    </>
  );
}

test('settings that were never saved are the defaults', () => {
  expect(parseSettings(null)).toEqual(DEFAULT_SETTINGS);
});

test.each([
  ['not json', DEFAULT_SETTINGS],
  ['[1, 2]', DEFAULT_SETTINGS],
  ['{"font": "comic", "size": 2, "theme": "dark"}', { ...DEFAULT_SETTINGS, size: 2, theme: 'dark' }],
  ['{"font": "sans", "size": 9, "theme": "sepia"}', { ...DEFAULT_SETTINGS, font: 'sans' }],
  ['{"font": "sans", "size": 1.5}', { ...DEFAULT_SETTINGS, font: 'sans' }],
])('stored %s reads back field by field', (raw, expected) => {
  expect(parseSettings(raw)).toEqual(expected);
});

test('a change is kept on the device and comes back next time', async () => {
  const first = await render(
    <ReaderSettingsProvider>
      <Probe />
    </ReaderSettingsProvider>,
  );
  await fireEvent.press(screen.getByRole('button', { name: 'Change' }));
  await waitFor(() => expect(AsyncStorage.setItem).toHaveBeenCalled());
  await first.unmount();

  await render(
    <ReaderSettingsProvider>
      <Probe />
    </ReaderSettingsProvider>,
  );

  expect(
    await screen.findByText(JSON.stringify({ font: 'serif', size: 4, theme: 'dark' })),
  ).toBeOnTheScreen();
});

test('storage that fails leaves the reader with the defaults', async () => {
  jest.mocked(AsyncStorage.getItem).mockRejectedValueOnce(new Error('denied'));

  await render(
    <ReaderSettingsProvider>
      <Probe />
    </ReaderSettingsProvider>,
  );
  await act(async () => {});

  expect(screen.getByText(JSON.stringify(DEFAULT_SETTINGS))).toBeOnTheScreen();
});
