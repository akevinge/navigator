import LaunchItem from './launch-item.svelte';
import LaunchList from './launch-list.svelte';
import LaunchListSkeleton from './launch-list-skeleton.svelte';
import LaunchCreateDialog from './launch-create-dialog.svelte';

export type LaunchListProps = {
	launches: { name: string; selected: boolean }[];
	onLaunchSelect: (index: number) => void;
};

export type LaunchItemProps = {
	name: string;
	selected?: boolean;
	index: number;
	onClick: (index: number) => void;
};

export { LaunchItem, LaunchList, LaunchListSkeleton, LaunchCreateDialog };