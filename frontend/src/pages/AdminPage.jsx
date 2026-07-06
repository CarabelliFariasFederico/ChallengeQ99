import CredentialsSection from "../admin/CredentialsSection.jsx";
import PermissionsMatrix from "../admin/PermissionsMatrix.jsx";
import TeamsSection from "../admin/TeamsSection.jsx";

export default function AdminPage() {
  return (
    <div className="screen screen-wide">
      <CredentialsSection />
      <PermissionsMatrix />
      <TeamsSection />
    </div>
  );
}
