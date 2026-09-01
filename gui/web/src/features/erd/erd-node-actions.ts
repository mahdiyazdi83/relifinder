import { createContext, useContext } from "react";

const ErdNodeActionsContext = createContext<{ toggleExpanded: (tableId: string) => void } | null>(
  null,
);

export const ErdNodeActionsProvider = ErdNodeActionsContext.Provider;

export function useErdNodeActions() {
  const context = useContext(ErdNodeActionsContext);
  if (!context) throw new Error("ERD node actions are unavailable.");
  return context;
}
