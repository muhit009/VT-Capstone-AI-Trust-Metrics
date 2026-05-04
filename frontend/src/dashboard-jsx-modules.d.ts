declare module '@/pages/AnalystChat' {
  import type { FC } from 'react';
  const AnalystChat: FC;
  export default AnalystChat;
}

declare module '@/pages/FlaggedOutputs' {
  import type { FC } from 'react';
  const FlaggedOutputs: FC;
  export default FlaggedOutputs;
}

declare module '@/pages/Analytics' {
  import type { FC } from 'react';
  const Analytics: FC;
  export default Analytics;
}

declare module '@/pages/Settings' {
  import type { FC } from 'react';
  const Settings: FC;
  export default Settings;
}

declare module '@/components/dashboard/Sidebar' {
  import type { FC } from 'react';
  const Sidebar: FC;
  export default Sidebar;
}

declare module '@/components/dashboard/TopBar' {
  import type { FC } from 'react';

  interface TopBarProps {
    title?: string;
    description?: string;
  }

  const TopBar: FC<TopBarProps>;
  export default TopBar;
}
