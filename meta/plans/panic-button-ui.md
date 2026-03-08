---
SECTION_ID: plans.panic-button-ui
TYPE: plan
STATUS: in_progress
PRIORITY: critical
---

# TASK-040: UI Panic Button (Big Red Button)

GOAL: Implement critical safety UI component for emergency trading halt
TIMELINE: Immediate

## Task Checklist

### Phase 1: Frontend Setup (TASK-034 prerequisite)
- [*] Initialize React + Vite + Tailwind project
- [ ] Create basic project structure
- [ ] Install dependencies (socket.io-client)

### Phase 2: Panic Button Component
- [ ] Create PanicButton React component
- [ ] Implement visual styling (red, large, pulsing)
- [ ] Add confirmation dialog
- [ ] Add status feedback (active/halted)

### Phase 3: Socket.io Integration
- [ ] Create Socket.io context/hook
- [ ] Implement HALT event emission
- [ ] Handle server responses

### Phase 4: Backend Integration
- [ ] Create Socket.io server endpoint
- [ ] Connect to cancel_all_orders functionality
- [ ] Add panic switch status broadcasting

### Phase 5: Testing
- [ ] Test button click → HALT command
- [ ] Verify orders cancelled
- [ ] Test visual feedback

## Success Criteria
- [ ] Large red button visible in UI
- [ ] Confirmation dialog appears before action
- [ ] HALT command sent to server on confirm
- [ ] Orders cancelled successfully
- [ ] Status feedback shows system state