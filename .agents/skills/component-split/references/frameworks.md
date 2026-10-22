# Framework-Specific Component Split Patterns

## React

### Extracting Logic → Custom Hook
```jsx
// Before: logic embedded in component
function UserProfile({ userId }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(`/api/users/${userId}`).then(r => r.json()).then(data => {
      setUser(data);
      setLoading(false);
    });
  }, [userId]);
  return loading ? <Spinner /> : <div>{user.name}</div>;
}

// After: hook extracts the data concern
function useUser(userId) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { /* same fetch */ }, [userId]);
  return { user, loading };
}

function UserProfile({ userId }) {
  const { user, loading } = useUser(userId);
  return loading ? <Spinner /> : <UserCard user={user} />;
}
```

### Container / Presenter Split
```jsx
// Container: knows about data
function UserProfileContainer({ userId }) {
  const { user, loading, error } = useUser(userId);
  if (loading) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;
  return <UserProfileView user={user} />;
}

// Presenter: knows about display only
function UserProfileView({ user }) {
  return (
    <div>
      <UserAvatar src={user.avatar} />
      <UserDetails name={user.name} bio={user.bio} />
    </div>
  );
}
```

### Compound Components Pattern (for tightly coupled UI)
```jsx
// Instead of a mega-prop approach:
// <Card title="..." footer="..." hasImage={true} imageUrl="..." />

// Use compound components:
<Card>
  <Card.Image src="..." />
  <Card.Title>Hello</Card.Title>
  <Card.Footer>...</Card.Footer>
</Card>
```

---

## Vue 3 (Composition API)

### Extracting Logic → Composable
```vue
<!-- Before: logic in setup() -->
<script setup>
const user = ref(null);
const loading = ref(true);
onMounted(async () => {
  user.value = await fetchUser(props.userId);
  loading.value = false;
});
</script>

<!-- After: extract to composable -->
// useUser.js
export function useUser(userId) {
  const user = ref(null);
  const loading = ref(true);
  onMounted(async () => {
    user.value = await fetchUser(userId);
    loading.value = false;
  });
  return { user, loading };
}

<!-- Component stays clean -->
<script setup>
const { user, loading } = useUser(props.userId);
</script>
```

### Vue Options API: Extracting Mixins → Composables
When modernizing Options API components, prefer composables over mixins. Mixins cause namespace collisions; composables are explicit.

---

## Svelte

### Extracting Stores
```svelte
<!-- Before: state in component -->
<script>
  let count = 0;
  function increment() { count++; }
</script>

<!-- After: writable store if shared across components -->
// counterStore.js
import { writable } from 'svelte/store';
export const count = writable(0);
export const increment = () => count.update(n => n + 1);
```

### Splitting Svelte Components
Svelte files are naturally scoped — split at logical UI boundaries. Use `$$props` forwarding for wrapper components:
```svelte
<!-- Button.svelte -->
<button {...$$props} on:click>
  <slot />
</button>
```

---

## Angular

### Extracting Services
Logic (HTTP calls, business rules, shared state) goes into `@Injectable` services. Components should only handle template interaction.

```typescript
// Before: HTTP in component
@Component({...})
export class UserComponent {
  user: User;
  constructor(private http: HttpClient) {
    this.http.get<User>('/api/user').subscribe(u => this.user = u);
  }
}

// After: service handles data
@Injectable({ providedIn: 'root' })
export class UserService {
  getUser(): Observable<User> {
    return this.http.get<User>('/api/user');
  }
}

@Component({...})
export class UserComponent implements OnInit {
  user: User;
  constructor(private userService: UserService) {}
  ngOnInit() { this.userService.getUser().subscribe(u => this.user = u); }
}
```

### Smart / Dumb Component Pattern in Angular
- **Smart (container)**: `UserContainerComponent` — injects services, handles routing
- **Dumb (presentational)**: `UserCardComponent` — only `@Input()` and `@Output()`, no service injection

---

## Plain JS / Web Components

### Module Extraction Pattern
```js
// Before: one big file
// ui.js — 400 lines of mixed concerns

// After: split by concern
// ui/modal.js      — modal open/close/render
// ui/form.js       — form validation and submission
// ui/table.js      — table rendering and sorting
// ui/index.js      — re-exports all UI utilities
```

### Custom Elements
When splitting a large custom element, extract sub-elements:
```js
// Before: <user-dashboard> does everything
// After:
// <user-profile> — avatar, name, bio
// <user-stats>   — activity metrics
// <user-actions> — follow, message, block buttons
// <user-dashboard> — composes the above
```