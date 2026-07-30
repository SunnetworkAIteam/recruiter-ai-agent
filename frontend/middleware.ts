import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// WHY an explicit allow-list of PUBLIC routes, not a block-list of
// protected ones: candidates applying to a job never have a Clerk
// account, so /apply/* must stay public. Every other route defaults to
// protected. An allow-list fails safe — if someone adds a new recruiter
// page and forgets to update this file, it's protected by default,
// which is the correct default for a system holding PII.
const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/apply(.*)",
  "/interview(.*)",
]);

export default clerkMiddleware((auth, req) => {
  if (!isPublicRoute(req)) {
    auth().protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
