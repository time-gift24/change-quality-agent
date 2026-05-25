import { getOrderedNodeIds, type RunViewState } from "../reducer";

type RunNodeListProps = {
  state: RunViewState;
  registeredNodeIds: string[];
};

export function RunNodeList({ state, registeredNodeIds }: RunNodeListProps) {
  const nodeIds = getOrderedNodeIds(state, registeredNodeIds);

  return (
    <section
      aria-label="Run nodes"
      className="rounded-lg border border-[#e5e7eb] bg-white"
    >
      <div className="border-b border-[#e5e7eb] px-4 py-3">
        <h2 className="m-0 text-sm font-medium text-[#212121]">Nodes</h2>
      </div>
      <ol className="m-0 list-none divide-y divide-[#e5e7eb] p-0">
        {nodeIds.map((nodeId) => {
          const node = state.nodes[nodeId];

          return (
            <li
              className="flex items-center justify-between gap-3 px-4 py-2 text-sm"
              key={nodeId}
            >
              <span
                className="min-w-0 truncate font-medium text-[#212121]"
                data-testid="run-node-id"
              >
                {nodeId}
              </span>
              <span className="shrink-0 rounded border border-[#e5e7eb] bg-[#eeece7] px-2 py-0.5 text-xs text-[#616161]">
                {node.status}
              </span>
            </li>
          );
        })}
        {nodeIds.length === 0 ? (
          <li className="px-4 py-3 text-sm text-[#616161]">No nodes yet</li>
        ) : null}
      </ol>
    </section>
  );
}
