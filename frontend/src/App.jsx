// frontend/src/App.jsx
"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Routes, Route, useLocation, Navigate } from "react-router-dom"

import Home from "./pages/Home"
import Menu from "./pages/Menu"
import About from "./pages/About"
import Reservations from "./pages/Reservations"
import Gallery from "./pages/Gallery"
import Navigation from "./components/Navigation"
import Footer from "./components/Footer"
import { ThemeProvider } from "./components/ThemeProvider"
import { ToastContainer } from "react-toastify"
import "react-toastify/dist/ReactToastify.css"

import AdminLogin from "./pages/admin/AdminLogin"
import AdminLayout from "./pages/AdminLayout"
import AdminReservations from "./pages/Admin"
import Dashboard from "./pages/admin/Dashboard"
import Customers from "./pages/admin/Customers"
import Newsletter from "./pages/admin/Newsletter"
import Blocks from "./pages/admin/Blocks"
import AuditLog from "./pages/admin/AuditLog"
import { adminService } from "./services/api"


function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

const pageVariants = {
  initial: { opacity: 0, scale: 0.95 },
  in: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
}

const pageTransition = {
  type: "tween",
  ease: "circOut",
  duration: 1.2,
}

const PageTransition = ({ children }) => (
  <motion.div initial="initial" animate="in" exit="out" variants={pageVariants} transition={pageTransition}>
    {children}
  </motion.div>
)

function ProtectedRoute({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(null) 

  useEffect(() => {
    const checkAuth = async () => {
      try {

        await adminService.getProfile()
        setIsAuthenticated(true)
      } catch {
        setIsAuthenticated(false)
      }
    }
    checkAuth()
  }, [])

  if (isAuthenticated === null) {
    return <div className="flex justify-center items-center min-h-screen">Loading...</div>
  }

  return isAuthenticated ? children : <Navigate to="/admin" replace />
}

function App() {
  const location = useLocation()
  const isAdminRoute = location.pathname.startsWith("/admin")

  return (

    <ThemeProvider>
      <div className="min-h-screen flex flex-col bg-background text-foreground">
        <ScrollToTop />

        {/* --- CONDITIONAL NAVIGATION AND FOOTER --- */}
        {!isAdminRoute && <Navigation />}

        <main className="flex-grow">
          <AnimatePresence>
            <Routes location={location} key={location.pathname}>
              {/* --- PUBLIC ROUTES --- */}
              <Route
                path="/"
                element={
                  <PageTransition>
                    <Home />
                  </PageTransition>
                }
              />
              <Route
                path="/menu"
                element={
                  <PageTransition>
                    <Menu />
                  </PageTransition>
                }
              />
              <Route
                path="/about"
                element={
                  <PageTransition>
                    <About />
                  </PageTransition>
                }
              />
              <Route
                path="/reservations"
                element={
                  <PageTransition>
                    <Reservations />
                  </PageTransition>
                }
              />
              <Route
                path="/gallery"
                element={
                  <PageTransition>
                    <Gallery />
                  </PageTransition>
                }
              />

              <Route path="/admin" element={<AdminLogin />} />
              <Route
                path="/admin/*"
                element={
                  <ProtectedRoute>
                    <AdminRoutes />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </AnimatePresence>
        </main>

        {!isAdminRoute && <Footer />}

        <ToastContainer
          position="bottom-right"
          autoClose={5000}
          hideProgressBar={false}
          newestOnTop={false}
          closeOnClick
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
          theme="light"
        />
      </div>
    </ThemeProvider>
  )
}

function AdminRoutes() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="reservations" element={<AdminReservations />} /> 
        <Route path="blocks" element={<Blocks />} />
        <Route path="customers" element={<Customers />} />
        <Route path="newsletter" element={<Newsletter />} />

        <Route path="audit" element={<AuditLog />} />

        <Route index element={<Navigate to="dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default App
