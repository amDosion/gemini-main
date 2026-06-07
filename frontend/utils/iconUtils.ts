
import {
  type LucideIcon,
  MessageSquare, Code2, Globe, PenTool, Brain, Terminal,
  User, Bot, Zap, Sparkles, Smile, Gavel, Stethoscope,
  Palette, Calculator, Briefcase, GraduationCap, Microscope,
  Shield, Rocket, Camera, Image, Brush, ScanFace, StickyNote, Layers, FileText
} from 'lucide-react';

export const ICON_MAP: Record<string, LucideIcon> = {
  MessageSquare, Code2, Globe, PenTool, Brain, Terminal,
  User, Bot, Zap, Sparkles, Smile, Gavel, Stethoscope,
  Palette, Calculator, Briefcase, GraduationCap, Microscope,
  Shield, Rocket, Camera, Image, Brush, ScanFace, StickyNote, Layers, FileText
};

export const getPersonaIcon = (iconName: string): LucideIcon => {
  return ICON_MAP[iconName] ?? MessageSquare;
};

export const AVAILABLE_ICONS = Object.keys(ICON_MAP);
