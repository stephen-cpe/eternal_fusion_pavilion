"use client"

import { useState, useEffect, useRef } from "react"
import { NavLink, useNavigate } from "react-router-dom"
import { adminService } from "../services/api"
import { toast } from "react-toastify"
import ChangeNameModal from "./ChangeNameModal"
import ChangePasswordModal from "./ChangePasswordModal"

function AdminNavigation() {
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const navigate = useNavigate()
  const profileRef = useRef(null)

  const [profileData, setProfileData] = useState({ fullName: "Admin User", email: "admin@efp.com" })
  const [isChangeNameModalOpen, setChangeNameModalOpen] = useState(false)
  const [isChangePasswordModalOpen, setChangePasswordModalOpen] = useState(false)

  const fetchProfile = async () => {
    try {
      const data = await adminService.getProfile()
      setProfileData({
        fullName: data.fullName,
        email: `${data.username}@efp.com`,
      })
    } catch (error) {
      toast.error("Could not load profile data.")
    }
  }

  useEffect(() => {
    fetchProfile()
  }, [])

  const handleLogout = async () => {
    try {
      await adminService.logout()
      toast.success("Logged out successfully")
      navigate("/admin") // Redirect to login page
    } catch (error) {
      toast.error(error.message || "Logout failed")
    }
  }

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setIsProfileOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [])

  const navItems = [
    { name: "Dashboard", path: "/admin/dashboard" },
    { name: "Reservations", path: "/admin/reservations" },
    { name: "Blocks", path: "/admin/blocks" },
    { name: "Customers", path: "/admin/customers" },
    { name: "Newsletter", path: "/admin/newsletter" },
    { name: "Audit Log", path: "/admin/audit" },
  ]

  return (
    <>
      <nav className="bg-deep-blue shadow-lg">
        <div className="container mx-auto px-4">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <span className="text-2xl font-bold text-golden-brown">Eternal Fusion Pavilion</span>
              <div className="hidden md:flex items-center space-x-1">
                {navItems.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.path}
                    className={({ isActive }) =>
                      `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-darker-blue text-primary-foreground"
                          : "text-lighter-blue hover:bg-darker-blue hover:text-white"
                      }`
                    }
                  >
                    {item.name}
                  </NavLink>
                ))}
              </div>
            </div>

            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                aria-expanded={isProfileOpen}
                aria-haspopup="menu"
                className="flex text-sm bg-darker-blue rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-deep-blue focus:ring-white"
              >
                <span className="sr-only">Open user menu</span>
                <img className="h-12 w-12 rounded-full object-cover" src="/admin-placholder.jpeg" alt="Admin Profile" />
              </button>
              {isProfileOpen && (
                <div className="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-lg py-1 bg-popover ring-1 ring-black/5 focus:outline-none">
                  <div className="px-4 py-2 text-sm text-foreground border-b border-border">

                    <p className="font-semibold">{profileData.fullName}</p>
                    <p className="text-xs text-muted-foreground">{profileData.email}</p>
                  </div>

                  <button
                    onClick={() => setChangeNameModalOpen(true)}
                    className="w-full text-left block px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Change Name
                  </button>
                  <button
                    onClick={() => setChangePasswordModalOpen(true)}
                    className="w-full text-left block px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Change Password
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left block px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Log Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
      <ChangeNameModal
        isOpen={isChangeNameModalOpen}
        onClose={() => setChangeNameModalOpen(false)}
        currentName={profileData.fullName}
        onSuccess={fetchProfile} // Re-fetch data on success
      />
      <ChangePasswordModal isOpen={isChangePasswordModalOpen} onClose={() => setChangePasswordModalOpen(false)} />
    </>
  )
}

export default AdminNavigation
