import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
// 24-core machine with 16 GB RAM: 12 render tabs keeps it busy without swapping.
Config.setConcurrency(12);
